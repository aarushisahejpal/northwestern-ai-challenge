"""industry-review-packager — one command generates (or regenerates) a full
industry review package from the built DuckDB and a per-industry spec file.

    python skills/industry-review-packager/scripts/lda_package_industry.py \
        skills/industry-review-packager/specs/<pkg>.json

Output: out/packages/<id>/  — data/*.csv (every row citation-keyed), an
interactive dashboard HTML, a README skeleton (only if none exists), and a zip.

Naming convention: the `lda_` prefix marks scripts that need the BUILT DuckDB
(lda-corpus-loader + lda-entity-resolver + lead-scanner's `lda_industry_map.py
--build-tags` for facet-lens packages).

Two lenses (spec `lens.type`):
  facet       — the industry lives in the lobbying free-text; scope = filings
                tagged in `lobbying_issue_mentions` for one curated lexicon tag
                (industry_lexicon.json). The crypto / pardons pattern.
  issue_codes — the industry is ALI-code-visible; scope = filings whose senate
                activities carry one of the spec'd codes. The healthcare pattern.

Invariant core (written once, guards baked in — see reference/corpus-profile.md):
  * senate-primary, never sum the two chambers (§1/§3)
  * amendment dedup on (registrant_id, client_id, filing_year, filing_period),
    latest by posted; registrations (R*) excluded from dollar work (§3)
  * client spend only via v_client_canonical_spend (P1, §4)
  * the safe entity_aliases join — ALWAYS through a DISTINCT subquery (§4 trap:
    one row per registrant-scoped senate_id per raw_name fans out per-row joins)
  * terminations DECLARED only: filing_type ~ '^[1-4](T|TY|@|@Y)$' (§3)
  * per-item dollars are ranking signals (attribution grain is filing-level)

Reconciliation assertions are BUILD FAILURES, not conventions: the quarterly
trend chart must equal its click-through list per quarter; per-player filing
counts must equal the raw-filing index; press chart counts must equal the
release list; spend bars must equal their quarter rows. Any mismatch aborts
the build with a non-zero exit.

What stays human (the spec CARRIES it; this script only assembles): lexicon
facets, roster/class hand-triage files, KPI copy, caveat prose, per-widget card
copy, README narrative.
"""
import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
REPO = SKILL.parent.parent
VIZ = SKILL / "viz"

QORD = ("CASE {col} WHEN 'first_quarter' THEN 1 WHEN 'second_quarter' THEN 2 "
        "WHEN 'third_quarter' THEN 3 ELSE 4 END")
PQ2 = {"first_quarter": "Q1", "second_quarter": "Q2", "third_quarter": "Q3",
       "fourth_quarter": "Q4", "mid_year": "MY", "year_end": "YE"}
LDA_FILING = "https://lda.senate.gov/filings/public/filing/{}/print/"
LDA_CONTRIB = "https://lda.senate.gov/filings/public/contribution/{}/print/"

# The corpus-profile §4 safe alias join — the ONE place it is written.
ALIAS_JOIN = ("LEFT JOIN (SELECT DISTINCT raw_name, entity_id FROM entity_aliases\n"
              "             WHERE kind='client' AND dataset='senate') ea "
              "ON ea.raw_name=sf.client_name\n"
              "  LEFT JOIN entities e ON e.entity_id=ea.entity_id")

CODE_NAMES = {"FIN": "Financial institutions & securities", "BAN": "Banking", "TAX": "Taxation",
    "SCI": "Science & technology", "CPI": "Computer industry", "CDT": "Commodities trading",
    "AGR": "Agriculture", "ACC": "Accounting", "GOV": "Government issues", "TRD": "Trade",
    "LAW": "Law enforcement & crime", "SMB": "Small business", "TEC": "Telecommunications",
    "CSP": "Consumer safety", "HOM": "Homeland security", "ENG": "Energy & nuclear",
    "RET": "Retirement", "URB": "Urban development", "MON": "Money & gold standard",
    "BUD": "Budget & appropriations", "FOR": "Foreign relations", "DEF": "Defense",
    "(none)": "(no code recorded)", "CIV": "Civil rights & civil liberties",
    "IND": "Indian/Native American affairs", "CON": "Constitution", "IMM": "Immigration",
    "EDU": "Education", "ALC": "Alcohol & drug abuse", "REL": "Religion", "JUD": "Judiciary",
    "MED": "Medical research", "FAM": "Family issues", "WEL": "Welfare", "VET": "Veterans",
    "LBR": "Labor", "ENV": "Environment & Superfund", "NAT": "Natural resources",
    "MIN": "Mining", "TRA": "Transportation", "AUT": "Automotive industry",
    "MAN": "Manufacturing", "AER": "Aerospace", "CHM": "Chemical industry",
    "FUE": "Fuel, gas & oil", "UTI": "Utilities", "CLE": "Clean air & water",
    "AVI": "Aviation/Airlines/Airports", "RRR": "Railroads", "TRU": "Trucking/Shipping",
    "MAR": "Marine/Maritime/Boating/Fisheries", "ROD": "Roads/Highway"}

FIX = {"Pac": "PAC", "Llc": "LLC", "Llp": "LLP", "Usa": "USA", "Us": "U.S.", "Rep": "Rep.",
       "Sen": "Sen.", "Jr": "Jr.", "Dc": "DC", "Ii": "II", "Iii": "III", "Aha": "AHA",
       "Ama": "AMA", "Ahip": "AHIP", "Aarp": "AARP", "Phrma": "PhRMA"}


def tcase(s):
    if not s or s != s.upper():
        return s
    return " ".join(FIX.get(w.strip(".,;"), w) for w in s.title().split())


SUFFIX = re.compile(r"\b(incorporated|inc|llc|l\.l\.c|corp|corporation|company|co|ltd|lp|pllc|plc|n\.?a)\b\.?,?", re.I)


def shorten(name, shorts=None):
    key = name.upper().strip()
    if shorts and key in shorts:
        return shorts[key]
    n = re.sub(r"\(.*?\)", "", name)
    n = n.split(" d/b/a ")[-1] if " d/b/a " in n.lower() else n
    n = n.split(",")[0]
    n = SUFFIX.sub("", n).strip(" ,.")
    n = re.sub(r"\s+", " ", n)
    if len(n) > 17:
        w = n.split()
        n = " ".join(w[:2])
        if len(n) > 17:
            n = w[0][:16]
    return n


def q_label(year, period):
    return f"{year}-{PQ2.get(period, period)}"


def num(v):
    if v in (None, "", "None"):
        return None
    return float(v)


class BuildFailure(SystemExit):
    pass


class Packager:
    def __init__(self, spec_path, db, out_root, baseline_root, gendate, args):
        self.spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        self.args = args
        self.id = self.spec["id"]
        self.p = self.spec["lens"].get("file_prefix", self.id)
        self.lens = self.spec["lens"]
        self.tok = self.lens.get("col_token", self.p)
        self.gendate = gendate or self.spec.get("gendate") or date.today().isoformat()
        self.db_path = Path(db) if db else REPO / "db" / "lda_full.duckdb"
        self.out_root = Path(out_root) if out_root else REPO / "out" / "packages"
        self.baseline_root = Path(baseline_root) if baseline_root else REPO / "out" / "packages"
        self.pkg_dir = self.out_root / self.id
        self.data_dir = self.pkg_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        import duckdb
        self.con = duckdb.connect(str(self.db_path), read_only=True)
        self.sql_log = {}          # csv name -> the exact SQL that produced it
        self.rows = {}             # csv name -> rows (for reconciliation + assembly)
        self.cols = {}             # csv name -> column list
        self.failures = []
        self.class_triage = self._load_class_triage()
        # facet tag / issue codes, validated (they are interpolated into SQL)
        if self.lens["type"] == "facet":
            self.tag = self.lens["tag"]
            assert re.fullmatch(r"[A-Z0-9_]+", self.tag), "facet tag must be [A-Z0-9_]+"
        else:
            self.codes = self.lens["codes"]
            assert all(re.fullmatch(r"[A-Z]{2,3}", c) for c in self.codes)
            self.codes_sql = "(" + ",".join(f"'{c}'" for c in self.codes) + ")"

    # ------------------------------------------------------------------ io
    def wcsv(self, name, cols, rows, sql=None):
        with open(self.data_dir / name, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        self.rows[name], self.cols[name] = rows, cols
        if sql:
            self.sql_log[name] = sql.strip()
        print(f"[csv] {name}: {len(rows)} rows")
        return rows

    def sql_csv(self, name, q):
        cur = self.con.execute(q)
        cols = [d[0] for d in cur.description]
        return self.wcsv(name, cols, cur.fetchall(), sql=q)

    def fail(self, msg):
        self.failures.append(msg)
        print(f"  [RECONCILE FAIL] {msg}")

    def gate(self, label):
        if self.failures:
            raise BuildFailure(f"BUILD FAILED at {label}: "
                               f"{len(self.failures)} reconciliation failure(s):\n  - "
                               + "\n  - ".join(self.failures))

    def _load_class_triage(self):
        cfg = self.spec.get("players", {}).get("class_triage_file")
        if not cfg:
            return None
        path = (SKILL / cfg) if (SKILL / cfg).exists() else (REPO / cfg)
        return json.loads(path.read_text(encoding="utf-8"))

    def classify(self, player):
        t = self.class_triage
        u = player.upper().strip()
        if u in t["classes"]:
            e = t["classes"][u]
            return e["class"], e.get("note", "")
        for cls, names in t.get("class_sets", {}).items():
            if u in names:
                return cls, ""
        d = t.get("default", {"class": "unclear", "note": ""})
        return d["class"], d.get("note", "")

    # ------------------------------------------------- scope CTE per lens
    def scope_cte(self):
        """CTE named `scope` = the senate filing_uuids in this package's scope."""
        if self.lens["type"] == "facet":
            return (f"scope AS (\n"
                    f"  SELECT DISTINCT lim.record_key AS filing_uuid\n"
                    f"  FROM lobbying_issue_mentions lim "
                    f"WHERE lim.tag='{self.tag}' AND lim.dataset='senate')")
        return (f"scope AS (\n"
                f"  SELECT DISTINCT a.filing_uuid FROM senate_activities a\n"
                f"  WHERE a.general_issue_code IN {self.codes_sql})")

    def kw_cte(self):
        # ORDER BY inside string_agg: deterministic output (regression-diffable)
        return (f"kw AS (\n"
                f"  SELECT record_key AS filing_uuid, string_agg(DISTINCT keyword, '; ' ORDER BY keyword) AS matched_keywords\n"
                f"  FROM lobbying_issue_mentions WHERE tag='{self.tag}' AND dataset='senate' GROUP BY 1)")

    # --------------------------------------------------------- exports
    def x_players(self):
        pl = self.spec.get("players", {})
        name_vis = pl.get("name_visibility_regex")
        tiers = pl.get("tiers")
        limit = pl.get("limit")
        acts = ""
        act_cols = ""
        act_join = ""
        if self.spec.get("modules", {}).get("activity_share") and self.lens["type"] == "facet":
            # Facet flavor of the activity-share metric (crypto, 2026-07-11
            # semantics): share of a client's senate free-text activity BLOCKS
            # that carry the facet tag. Same blocks-not-filings rationale as the
            # codes flavor below; numerator is the curated-lexicon tag. LEFT
            # JOIN so registration-only players band as 'n/a', not vanish.
            share = f"100.0*a.{self.tok}_activity_blocks/a.all_activity_blocks"
            acts = f""",
acts AS (
  SELECT coalesce(e.entity_id,'unresolved:'||sf.client_name) AS entity_id,
         count(*) AS all_activity_blocks,
         count(t.record_key) AS {self.tok}_activity_blocks
  FROM senate_filings sf
  JOIN lobbying_freetext lf ON lf.record_key=sf.filing_uuid AND lf.dataset='senate'
  {ALIAS_JOIN}
  LEFT JOIN (SELECT DISTINCT record_key, sub_index FROM lobbying_issue_mentions
             WHERE tag='{self.tag}' AND dataset='senate') t
         ON t.record_key=lf.record_key AND t.sub_index=lf.sub_index
  WHERE sf.client_name IS NOT NULL AND sf.filing_type NOT LIKE 'R%'
  GROUP BY 1)"""
            act_cols = (f"\n       a.{self.tok}_activity_blocks, a.all_activity_blocks,\n"
                        f"       round({share},1) AS {self.tok}_activity_share_pct,\n"
                        f"       CASE WHEN a.all_activity_blocks IS NULL THEN 'n/a (registrations only)'\n"
                        f"            WHEN {share} >= 25 THEN 'dedicated'\n"
                        f"            WHEN {share} >= 5 THEN 'engaged'\n"
                        f"            ELSE 'ambient' END AS {self.tok}_share_band,")
            act_join = "\nLEFT JOIN acts a USING (entity_id)"
        elif self.spec.get("modules", {}).get("activity_share"):
            # activity-level share (the healthcare species split): a self-filer's
            # single quarterly lists dozens of codes, so share is computed on
            # ACTIVITY rows, never filings. Alias join via the §4-safe DISTINCT.
            acts = f""",
acts AS (
  SELECT coalesce(e.entity_id,'unresolved:'||sf.client_name) AS entity_id,
         count(*) AS all_activities,
         sum(CASE WHEN a.general_issue_code IN {self.codes_sql} THEN 1 ELSE 0 END) AS {self.tok}_activities
  FROM senate_filings sf
  JOIN senate_activities a ON a.filing_uuid=sf.filing_uuid
  {ALIAS_JOIN}
  WHERE sf.client_name IS NOT NULL AND sf.filing_type NOT LIKE 'R%'
  GROUP BY 1)"""
            act_cols = (f"\n       a.{self.tok}_activities, a.all_activities,\n"
                        f"       round(100.0*a.{self.tok}_activities/a.all_activities,1) AS {self.tok}_activity_share_pct,")
            act_join = "\nJOIN acts a USING (entity_id)"
        extra_cols = ""
        if name_vis:
            core = tiers.get("core", 8) if tiers else 8
            act = tiers.get("active", 3) if tiers else 3
            extra_cols = (f",\n       CASE WHEN regexp_matches(p.player, '{name_vis}') THEN 'yes' ELSE 'no' END"
                          f" AS {self.tok}_term_in_name,\n"
                          f"       CASE WHEN p.{self.tok}_filings_senate>={core} THEN 'core'\n"
                          f"            WHEN p.{self.tok}_filings_senate>={act} THEN 'active'\n"
                          f"            ELSE 'peripheral' END AS tier")
        reg_filter = "" if self.lens["type"] == "facet" else " AND sf.filing_type NOT LIKE 'R%'"
        fcol = f"{self.tok}_filings_senate" if self.lens["type"] == "facet" else f"{self.tok}_filings"
        q = f"""
WITH {self.scope_cte()},
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year
  FROM scope c
  JOIN senate_filings sf ON sf.filing_uuid=c.filing_uuid
  {ALIAS_JOIN}
  WHERE sf.client_name IS NOT NULL{reg_filter}),
players AS (
  SELECT entity_id, any_value(player) AS player,
         count(DISTINCT filing_uuid) AS {fcol},
         min(filing_year) AS first_year, max(filing_year) AS last_year
  FROM resolved GROUP BY 1){acts},
spend AS (
  SELECT client_entity_id, round(sum(canonical_spend))::BIGINT AS total_all_issue_spend
  FROM v_client_canonical_spend GROUP BY 1)
SELECT p.player, p.entity_id, p.{fcol},{act_cols}
       p.first_year, p.last_year, s.total_all_issue_spend{extra_cols}
FROM players p{act_join} LEFT JOIN spend s ON s.client_entity_id=p.entity_id
ORDER BY {"s.total_all_issue_spend DESC NULLS LAST, p.player"
          if self.spec.get("modules", {}).get("activity_share") and self.lens["type"] != "facet"
          else f"p.{fcol} DESC, s.total_all_issue_spend DESC NULLS LAST, p.player"}
{f"LIMIT {int(limit)}" if limit else ""}"""
        name = f"{self.p}_players.csv"
        if self.class_triage:
            cur = self.con.execute(q)
            cols = [d[0] for d in cur.description]
            rows = [list(r) + list(self.classify(r[0])) for r in cur.fetchall()]
            self.wcsv(name, cols + ["client_class", "class_note"], rows, sql=q)
        else:
            self.sql_csv(name, q)
        return name

    def x_player_filings(self):
        """Raw-filing index behind every player — same join as the players
        export, so per-player counts reconcile with the map (gated below)."""
        q = f"""
WITH {self.scope_cte()},
{self.kw_cte()},
resolved AS (
  SELECT DISTINCT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         k.matched_keywords
  FROM scope c
  JOIN senate_filings sf ON sf.filing_uuid=c.filing_uuid
  JOIN kw k ON k.filing_uuid=c.filing_uuid
  {ALIAS_JOIN}
  WHERE sf.client_name IS NOT NULL)
SELECT player, entity_id, filing_year, filing_period, filing_type,
       registrant_name, amount, matched_keywords, filing_uuid
FROM resolved
ORDER BY player, filing_year, filing_period, filing_uuid"""
        rows = self.con.execute(q).fetchall()
        name = f"{self.p}_player_filings.csv"
        self.wcsv(name,
                  ["player", "entity_id", "filing_year", "filing_period", "filing_type",
                   "registrant_name", "reported_amount", "matched_keywords", "filing_uuid",
                   "lda_public_url"],
                  [list(r) + [LDA_FILING.format(r[8])] for r in rows], sql=q)
        # gate: per-player distinct filing counts == the players export
        per = {}
        for r in rows:
            per.setdefault(r[0], set()).add(r[8])
        pcols = self.cols[f"{self.p}_players.csv"]
        fidx = pcols.index(f"{self.tok}_filings_senate")
        for pr in self.rows[f"{self.p}_players.csv"]:
            want, got = pr[fidx], len(per.get(pr[0], ()))
            if want != got:
                self.fail(f"player filings: {pr[0][:40]} players.csv={want} index={got}")
        self.gate("player-filings reconciliation")

    def x_trend(self):
        spendsel = spendjoin = spendcte = ""
        group_extra = ""
        scol = self.lens.get("spend_col", "canonical_spend_tagged_clients")
        if self.spec.get("modules", {}).get("trend_spend", True):
            spendcte = f""",
cq AS (SELECT DISTINCT ceid, filing_year, filing_period FROM ded),
spend AS (
  SELECT cq.filing_year, cq.filing_period, round(sum(v.canonical_spend))::BIGINT AS {scol}
  FROM cq JOIN v_client_canonical_spend v
    ON v.client_entity_id=cq.ceid AND v.filing_year=cq.filing_year AND v.filing_period=cq.filing_period
  GROUP BY 1,2)"""
            spendsel = f",\n       s.{scol}"
            spendjoin = " LEFT JOIN spend s ON s.filing_year=d.filing_year AND s.filing_period=d.filing_period"
            group_extra = f",s.{scol}"
        fcol, ccol = (f"{self.tok}_filings", f"{self.tok}_clients")
        q = f"""
WITH {self.scope_cte()},
ded AS (
  SELECT sf.*, coalesce(e.entity_id,'unresolved:'||sf.client_name) AS ceid
  FROM senate_filings sf
  JOIN scope t ON t.filing_uuid=sf.filing_uuid
  {ALIAS_JOIN}
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1){spendcte}
SELECT d.filing_year, d.filing_period,
       count(DISTINCT d.filing_uuid) AS {fcol},
       count(DISTINCT d.ceid) AS {ccol}{spendsel}
FROM ded d{spendjoin}
GROUP BY 1,2{group_extra}
ORDER BY 1, {QORD.format(col='d.filing_period')}"""
        self.sql_csv(f"{self.p}_quarterly_trend.csv", q)

    def x_trend_filings(self):
        """Click-through behind each trend quarter — EXACTLY the chart's dedup
        semantics, so per-quarter counts equal the plotted counts (gated)."""
        q = f"""
WITH {self.scope_cte()},
ded AS (
  SELECT sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name,
         coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM senate_filings sf
  JOIN scope t ON t.filing_uuid=sf.filing_uuid
  {ALIAS_JOIN}
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1),
{self.kw_cte()}
SELECT DISTINCT d.filing_year, d.filing_period, d.player, d.registrant_name, d.amount,
       d.filing_type, k.matched_keywords, d.filing_uuid
FROM ded d LEFT JOIN kw k ON k.filing_uuid = d.filing_uuid
ORDER BY d.filing_year, d.filing_period, d.amount DESC NULLS LAST, d.filing_uuid"""
        rows = self.con.execute(q).fetchall()
        name = f"{self.p}_trend_filings.csv"
        self.wcsv(name,
                  ["filing_year", "filing_period", "player", "registrant_name",
                   "reported_amount", "filing_type", "matched_keywords", "filing_uuid",
                   "lda_public_url"],
                  [list(r) + [LDA_FILING.format(r[7])] for r in rows], sql=q)
        perq = {}
        for r in rows:
            perq[(str(r[0]), r[1])] = perq.get((str(r[0]), r[1]), 0) + 1
        tcols = self.cols[f"{self.p}_quarterly_trend.csv"]
        fidx = tcols.index(f"{self.tok}_filings")
        for tr in self.rows[f"{self.p}_quarterly_trend.csv"]:
            want, got = tr[fidx], perq.get((str(tr[0]), tr[1]), 0)
            if want != got:
                self.fail(f"trend: {tr[0]} {tr[1]} chart={want} click-through={got}")
        self.gate("trend reconciliation")

    def x_scatter(self):
        q = f"""
WITH docs AS (
  SELECT DISTINCT lim.doc_id, lf.issue_code
  FROM lobbying_issue_mentions lim JOIN lobbying_freetext lf USING (doc_id)
  WHERE lim.tag='{self.tag}')
SELECT coalesce(issue_code,'(none)') AS issue_code, count(*) AS {self.tok}_docs,
       round(100.0*count(*)/sum(count(*)) OVER (),1) AS pct_of_{self.tok}
FROM docs GROUP BY 1 ORDER BY {self.tok}_docs DESC, issue_code"""
        self.sql_csv(f"{self.p}_issue_code_scatter.csv", q)

    def x_scatter_filings(self):
        q = f"""
WITH cd AS (
  SELECT DISTINCT lim.doc_id, coalesce(lf.issue_code,'(none)') AS issue_code,
         lim.dataset, lim.record_key, lim.keyword
  FROM lobbying_issue_mentions lim JOIN lobbying_freetext lf USING (doc_id)
  WHERE lim.tag='{self.tag}'),
sen AS (
  SELECT issue_code, record_key AS filing_uuid, count(DISTINCT doc_id) AS n_blocks,
         string_agg(DISTINCT keyword, '; ' ORDER BY keyword) AS matched_keywords
  FROM cd WHERE dataset='senate' GROUP BY 1, 2)
SELECT DISTINCT s.issue_code,
       coalesce(e.canonical_name, sf.client_name) AS player,
       sf.registrant_name, sf.filing_year, sf.filing_period,
       coalesce(sf.income, sf.expenses)::BIGINT AS reported_amount,
       s.n_blocks, s.matched_keywords, s.filing_uuid
FROM sen s
JOIN senate_filings sf ON sf.filing_uuid = s.filing_uuid
{ALIAS_JOIN}
ORDER BY s.issue_code, reported_amount DESC NULLS LAST, s.filing_uuid"""
        rows = self.con.execute(q).fetchall()
        self.wcsv(f"{self.p}_issue_code_filings.csv",
                  ["issue_code", "player", "registrant_name", "filing_year", "filing_period",
                   "reported_amount", f"n_{self.tok}_blocks_in_filing", "matched_keywords",
                   "filing_uuid", "lda_public_url"],
                  [list(r) + [LDA_FILING.format(r[8])] for r in rows], sql=q)

    def x_keywords(self):
        q = (f"SELECT keyword, count(DISTINCT record_key) AS filings\n"
             f"FROM lobbying_issue_mentions WHERE tag='{self.tag}' "
             f"GROUP BY 1 ORDER BY filings DESC, keyword")
        self.sql_csv(f"{self.p}_keywords.csv", q)

    def x_registrants(self):
        limit = self.spec.get("modules", {}).get("registrants_limit", 60)
        fcol = f"{self.tok}_filings"
        q = f"""
WITH {self.scope_cte()},
ded AS (
  SELECT sf.* FROM senate_filings sf JOIN scope t ON t.filing_uuid=sf.filing_uuid
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT registrant_name,
       count(DISTINCT filing_uuid) AS {fcol},
       count(DISTINCT client_id) AS clients,
       round(sum(coalesce(income, expenses)))::BIGINT AS reported_amount_ranking_signal
FROM ded
WHERE upper(trim(registrant_name)) != upper(trim(client_name))  -- outside firms only
GROUP BY 1 ORDER BY {fcol} DESC, registrant_name LIMIT {int(limit)}"""
        self.sql_csv(f"{self.p}_registrant_firms.csv", q)

    def x_press(self):
        """Facet-lens press share: whole-word regex over member releases."""
        rx = self.spec["press"]["regex"].replace("'", "''")
        tok = self.spec["press"].get("col_token", self.tok)
        q = f"""
WITH pr AS (
  SELECT pr_id, date,
         (substr(date,1,4) || '-Q' || CAST(ceil(CAST(substr(date,6,2) AS INT)/3.0) AS INT)) AS quarter,
         regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')), '{rx}') AS is_hit
  FROM press_releases WHERE date >= '2022-01-01')
SELECT quarter, count(*) AS all_releases,
       sum(CASE WHEN is_hit THEN 1 ELSE 0 END) AS {tok}_releases,
       round(100.0*sum(CASE WHEN is_hit THEN 1 ELSE 0 END)/count(*),2) AS {tok}_share_pct
FROM pr GROUP BY 1 ORDER BY 1"""
        self.sql_csv(f"{self.p}_press_quarterly.csv", q)

    def x_press_releases(self):
        rx = self.spec["press"]["regex"].replace("'", "''")
        q = f"""
SELECT (substr(date,1,4) || '-Q' || CAST(ceil(CAST(substr(date,6,2) AS INT)/3.0) AS INT)) AS quarter,
       date, member_name, party, state, chamber, title, url,
       src_file, src_line
FROM press_releases
WHERE date >= '2022-01-01'
  AND regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')), '{rx}')
ORDER BY date, src_file, src_line"""
        rows = self.con.execute(q).fetchall()
        name = f"{self.p}_press_releases.csv"
        self.wcsv(name, ["quarter", "date", "member_name", "party", "state", "chamber",
                         "title", "url", "src_file", "src_line"], rows, sql=q)
        perq = {}
        for r in rows:
            perq[r[0]] = perq.get(r[0], 0) + 1
        tok = self.spec["press"].get("col_token", self.tok)
        pcols = self.cols[f"{self.p}_press_quarterly.csv"]
        nidx = pcols.index(f"{tok}_releases")
        for pr in self.rows[f"{self.p}_press_quarterly.csv"]:
            want, got = pr[nidx], perq.get(pr[0], 0)
            if want != got:
                self.fail(f"press: {pr[0]} chart={want} releases={got}")
        self.gate("press reconciliation")

    def x_samples(self):
        kw_sel, kw_join, kw_col = "", "", ""
        if self.lens["type"] == "facet":
            kw_sel = " t.keyword_example,"
            kw_col = "\n       keyword_example,"
            scope = (f"tagged AS (\n  SELECT lim.record_key AS filing_uuid, any_value(lim.keyword) AS keyword_example\n"
                     f"  FROM lobbying_issue_mentions lim WHERE lim.tag='{self.tag}' AND lim.dataset='senate' GROUP BY 1)")
            kw_join = "JOIN tagged t USING (filing_uuid)"
        else:
            scope = self.scope_cte().replace("scope AS", "tagged AS")
            kw_join = "JOIN tagged t ON t.filing_uuid=sf.filing_uuid"
        q = f"""
WITH {scope},
ranked AS (
  SELECT sf.client_name, sf.registrant_name, sf.filing_uuid,{kw_sel}
         sf.filing_year, sf.filing_period, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         row_number() OVER (PARTITION BY sf.client_name ORDER BY coalesce(sf.income, sf.expenses) DESC NULLS LAST) rn,
         count(*) OVER (PARTITION BY sf.client_name) n
  FROM senate_filings sf {kw_join})
SELECT client_name, registrant_name, filing_year, filing_period, amount,{kw_col}
       filing_uuid AS show_record_key
FROM ranked WHERE rn=1 ORDER BY n DESC, client_name LIMIT 25"""
        self.sql_csv(f"{self.p}_record_samples_qa.csv", q)

    def x_engagements(self):
        """Engagement grain = (registrant, client) pair among tagged filings;
        termination is the DECLARED T-family only (corpus-profile §3).
        REGISTRATION-ONLY declarations (the Zherka fix, d1b0c8c 2026-07-11): an
        engagement may state its purpose ONLY on the LD-1 registration while its
        LD-2 quarterlies carry no activity text. Such a quarter is credited only
        when the quarterly declares NO text of its own (income from quarters
        declaring other work is never re-attributed); tag_basis labels rows
        'registration-only' vs 'quarterly-text'."""
        q = f"""
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='{self.tag}' AND lim.dataset='senate'),
pairs AS (
  SELECT DISTINCT sf.registrant_id, sf.client_id,
         any_value(sf.registrant_name) OVER (PARTITION BY sf.registrant_id) AS registrant_name
  FROM senate_filings sf JOIN tagged t ON t.filing_uuid=sf.filing_uuid),
reg_tagged AS (
  SELECT sf.registrant_id, sf.client_id, min(sf.filing_uuid) AS reg_uuid
  FROM senate_filings sf JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  WHERE sf.filing_type LIKE 'R%' GROUP BY 1,2),
act_n AS (SELECT filing_uuid, count(*) AS n_act FROM senate_activities GROUP BY 1),
pf AS (
  SELECT sf.*, (t.filing_uuid IS NOT NULL) AS is_tagged,
         coalesce(a.n_act, 0) AS n_act,
         (rt.registrant_id IS NOT NULL) AS pair_reg_tagged, rt.reg_uuid,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM senate_filings sf
  JOIN pairs p ON p.registrant_id=sf.registrant_id AND p.client_id=sf.client_id
  LEFT JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  LEFT JOIN act_n a ON a.filing_uuid=sf.filing_uuid
  LEFT JOIN reg_tagged rt ON rt.registrant_id=sf.registrant_id AND rt.client_id=sf.client_id
  {ALIAS_JOIN}),
ded AS (
  SELECT *,
    bool_or(is_tagged) OVER (PARTITION BY registrant_id, client_id, filing_year, filing_period)
      OR (pair_reg_tagged AND max(n_act) OVER (PARTITION BY registrant_id, client_id,
            filing_year, filing_period) = 0) AS q_tagged,
    bool_or(is_tagged) OVER (PARTITION BY registrant_id, client_id, filing_year, filing_period) AS q_text_tagged
  FROM pf WHERE filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY registrant_id, client_id, filing_year, filing_period
                             ORDER BY posted DESC, filing_uuid DESC)=1),
term AS (
  SELECT registrant_id, client_id,
         max(filing_year||'-'||CASE filing_period WHEN 'first_quarter' THEN 'Q1' WHEN 'second_quarter' THEN 'Q2'
             WHEN 'third_quarter' THEN 'Q3' WHEN 'fourth_quarter' THEN 'Q4' ELSE filing_period END) AS termination_quarter
  FROM pf WHERE regexp_matches(filing_type, '^[1-4](T|TY|@|@Y)$')
  GROUP BY 1,2)
SELECT any_value(d.player) AS player, any_value(d.registrant_name) AS registrant_name,
       min(CASE WHEN d.q_tagged THEN d.filing_year||'-'||CASE d.filing_period WHEN 'first_quarter' THEN 'Q1'
           WHEN 'second_quarter' THEN 'Q2' WHEN 'third_quarter' THEN 'Q3' ELSE 'Q4' END END) AS first_tagged_quarter,
       max(CASE WHEN d.q_tagged THEN d.filing_year||'-'||CASE d.filing_period WHEN 'first_quarter' THEN 'Q1'
           WHEN 'second_quarter' THEN 'Q2' WHEN 'third_quarter' THEN 'Q3' ELSE 'Q4' END END) AS last_tagged_quarter,
       count(DISTINCT CASE WHEN d.q_tagged THEN d.filing_year||d.filing_period END) AS tagged_quarters,
       sum(CASE WHEN d.q_tagged THEN coalesce(d.income, d.expenses) END)::BIGINT AS reported_total_tagged_quarters,
       CASE WHEN any_value(t.termination_quarter) IS NOT NULL THEN 'yes' ELSE 'no' END AS terminated,
       any_value(t.termination_quarter) AS termination_quarter,
       coalesce(max(CASE WHEN d.q_text_tagged THEN d.filing_uuid END),
                any_value(d.reg_uuid)) AS sample_filing_uuid,
       CASE WHEN bool_or(d.q_text_tagged) THEN 'quarterly-text'
            ELSE 'registration-only' END AS tag_basis
FROM ded d LEFT JOIN term t ON t.registrant_id=d.registrant_id AND t.client_id=d.client_id
GROUP BY d.registrant_id, d.client_id
HAVING count(DISTINCT CASE WHEN d.q_tagged THEN d.filing_year||d.filing_period END) > 0
ORDER BY reported_total_tagged_quarters DESC NULLS LAST"""
        cur = self.con.execute(q)
        ecols = [d[0] for d in cur.description]
        erows = cur.fetchall()
        # min() not any_value(): the sample text pick must be deterministic
        txt_by_uuid = dict(self.con.execute(f"""
            SELECT lf.record_key, min(substr(lf.txt,1,220))
            FROM lobbying_freetext lf
            JOIN lobbying_issue_mentions lim ON lim.doc_id=lf.doc_id AND lim.tag='{self.tag}'
            WHERE lf.dataset='senate' GROUP BY 1""").fetchall())
        keep = self.spec.get("modules", {}).get("engagements")
        classes = keep.get("classes") if isinstance(keep, dict) else None
        out = []
        for r in erows:
            cls, _ = self.classify(r[0]) if self.class_triage else ("", "")
            if classes and cls not in classes:
                continue
            declared = " ".join((txt_by_uuid.get(r[8]) or "").split())
            out.append(list(r) + [cls, declared])
        out.sort(key=lambda x: -(x[5] or 0))
        self.wcsv(f"{self.p}_engagements.csv",
                  ecols + ["client_class", "declared_text_sample"], out, sql=q)

    def x_spend_quarters(self):
        q = f"""
WITH {self.scope_cte()},
players AS (
  SELECT DISTINCT coalesce(e.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM scope t
  JOIN senate_filings sf ON sf.filing_uuid = t.filing_uuid
  {ALIAS_JOIN}
  WHERE sf.client_name IS NOT NULL)
SELECT p.player, v.client_entity_id, v.filing_year, v.filing_period,
       v.has_inhouse_filing, v.inhouse_amount::BIGINT, v.outside_amount::BIGINT,
       v.canonical_spend::BIGINT, v.method, v.n_filings
FROM players p JOIN v_client_canonical_spend v ON v.client_entity_id = p.entity_id
ORDER BY p.player, v.filing_year, v.filing_period"""
        rows = self.con.execute(q).fetchall()
        self.wcsv(f"{self.p}_spend_quarters.csv",
                  ["player", "entity_id", "filing_year", "filing_period", "has_inhouse_filing",
                   "inhouse_amount", "outside_amount", "canonical_spend", "method", "n_filings"],
                  rows, sql=q)
        tot = {}
        for r in rows:
            tot[r[0]] = tot.get(r[0], 0) + (r[7] or 0)
        pcols = self.cols[f"{self.p}_players.csv"]
        sidx = pcols.index("total_all_issue_spend")
        for pr in self.rows[f"{self.p}_players.csv"]:
            want = pr[sidx]
            if want is None:
                continue
            if abs(tot.get(pr[0], 0) - float(want)) > 1:
                self.fail(f"spend: {pr[0][:40]} players.csv={want} quarter-sum={tot.get(pr[0])}")
        self.gate("spend reconciliation")

    def x_bills(self):
        limit = self.spec.get("modules", {}).get("bills", {})
        limit = limit.get("limit", 60) if isinstance(limit, dict) else 60
        q = f"""
WITH {self.scope_cte()}
SELECT b.bill,
       count(DISTINCT coalesce(e.canonical_name, sf.client_name)) AS clients,
       count(DISTINCT b.record_key) AS filings,
       min(sf.filing_year) AS first_year, max(sf.filing_year) AS last_year
FROM bill_mentions b
JOIN scope hc ON hc.filing_uuid=b.record_key
JOIN senate_filings sf ON sf.filing_uuid=b.record_key
{ALIAS_JOIN}
WHERE b.dataset='senate'
GROUP BY 1 ORDER BY clients DESC, bill LIMIT {int(limit)}"""
        self.sql_csv(f"{self.p}_bills.csv", q)

    # ------------------------------------------------ issue-codes extras
    def x_code_trend(self):
        q = f"""
WITH ded AS (
  SELECT sf.filing_uuid, sf.filing_year, sf.filing_period
  FROM senate_filings sf
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT d.filing_year, d.filing_period, a.general_issue_code,
       count(DISTINCT d.filing_uuid) AS filings
FROM ded d JOIN senate_activities a ON a.filing_uuid=d.filing_uuid
WHERE a.general_issue_code IN {self.codes_sql}
GROUP BY 1,2,3
ORDER BY 1, {QORD.format(col='d.filing_period')}, 3"""
        self.sql_csv(f"{self.p}_code_trend.csv", q)

    def x_press_coupling(self):
        tok = self.spec["press"].get("col_token", self.tok)
        scol = self.lens.get("spend_col", f"canonical_spend_{self.p}_clients")
        q = f"""
WITH pr AS (
  SELECT p.pr_id, (substr(p.date,1,4) || '-Q' || CAST(ceil(CAST(substr(p.date,6,2) AS INT)/3.0) AS INT)) AS quarter
  FROM press_releases p WHERE p.date >= '2022-01-01'),
tagged AS (
  SELECT DISTINCT m.pr_id FROM press_issue_mentions m WHERE m.issue_code IN {self.codes_sql}),
prq AS (
  SELECT pr.quarter, count(*) AS all_releases,
         sum(CASE WHEN t.pr_id IS NOT NULL THEN 1 ELSE 0 END) AS {tok}_releases
  FROM pr LEFT JOIN tagged t ON t.pr_id=pr.pr_id GROUP BY 1),
{self.scope_cte()},
ded AS (
  SELECT sf.*, coalesce(e.entity_id,'unresolved:'||sf.client_name) AS ceid
  FROM senate_filings sf JOIN scope hc ON hc.filing_uuid=sf.filing_uuid
  {ALIAS_JOIN}
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1),
cq AS (SELECT DISTINCT ceid, filing_year, filing_period FROM ded),
spendq AS (
  SELECT cq.filing_year || '-Q' || {QORD.format(col='cq.filing_period')} AS quarter,
         round(sum(v.canonical_spend))::BIGINT AS {scol}
  FROM cq JOIN v_client_canonical_spend v
    ON v.client_entity_id=cq.ceid AND v.filing_year=cq.filing_year AND v.filing_period=cq.filing_period
  GROUP BY 1)
SELECT prq.quarter, prq.{tok}_releases, prq.all_releases,
       round(100.0*prq.{tok}_releases/prq.all_releases,2) AS {tok}_press_share_pct,
       s.{scol}
FROM prq LEFT JOIN spendq s USING (quarter)
ORDER BY prq.quarter"""
        self.sql_csv(f"{self.p}_press_coupling.csv", q)

    def x_press_releases_codes(self):
        """issue_codes-lens counterpart to the facet lens's x_press_releases():
        the individual releases behind the press-coupling chart, so the
        dashboard can click through a quarter to the actual releases (same
        pattern as the facet lens and the legacy viz_build dashboards)."""
        tok = self.spec["press"].get("col_token", self.tok)
        q = f"""
WITH tagged AS (
  SELECT DISTINCT m.pr_id FROM press_issue_mentions m WHERE m.issue_code IN {self.codes_sql})
SELECT (substr(p.date,1,4) || '-Q' || CAST(ceil(CAST(substr(p.date,6,2) AS INT)/3.0) AS INT)) AS quarter,
       p.date, p.member_name, p.party, p.state, p.chamber, p.title, p.url,
       p.src_file, p.src_line
FROM press_releases p JOIN tagged t ON t.pr_id = p.pr_id
WHERE p.date >= '2022-01-01'
ORDER BY p.date, p.src_file, p.src_line"""
        rows = self.con.execute(q).fetchall()
        name = f"{self.p}_press_releases.csv"
        self.wcsv(name, ["quarter", "date", "member_name", "party", "state", "chamber",
                         "title", "url", "src_file", "src_line"], rows, sql=q)
        perq = {}
        for r in rows:
            perq[r[0]] = perq.get(r[0], 0) + 1
        pcols = self.cols[f"{self.p}_press_coupling.csv"]
        nidx = pcols.index(f"{tok}_releases")
        qidx = pcols.index("quarter")
        for pr in self.rows[f"{self.p}_press_coupling.csv"]:
            want, got = pr[nidx], perq.get(pr[qidx], 0)
            if want != got:
                self.fail(f"press: {pr[qidx]} chart={want} releases={got}")
        self.gate("press reconciliation")

    # ------------------------------------------------------------- roster
    def x_roster(self):
        cfg = self.spec.get("roster")
        if not cfg:
            return None
        if self.out_root != REPO / "out" / "packages":
            # regression/scratch mode: never overwrite the committed out/ roster —
            # write beside the regenerated package so the harness can diff it
            path = self.out_root / "_rosters" / Path(cfg["path"]).name
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = REPO / cfg["path"]
        top = cfg.get("top", 150)
        # Own full-DB query — NEVER derived from the players export, which may be
        # LIMITed on a different axis (spend): a high-filings/low-spend client
        # would silently drop out of the roster (the exact mistake the 2026-07-11
        # healthcare roster-resplit fix corrected).
        reg_filter = "" if self.lens["type"] == "facet" else " AND sf.filing_type NOT LIKE 'R%'"
        q = f"""
WITH {self.scope_cte()}
SELECT coalesce(e.canonical_name, sf.client_name) AS player,
       count(DISTINCT sf.filing_uuid) AS n
FROM scope c
JOIN senate_filings sf ON sf.filing_uuid=c.filing_uuid
{ALIAS_JOIN}
WHERE sf.client_name IS NOT NULL{reg_filter}
GROUP BY 1 ORDER BY n DESC, player LIMIT {int(top)}"""
        ranked = self.con.execute(q).fetchall()
        path.write_text("\n".join(r[0] for r in ranked) + "\n", encoding="utf-8")
        print(f"[roster] {path}: {len(ranked)} names (top {top} by tagged filings, full-DB query)")
        return path

    # ------------------------------------------------------------- giving
    def run_giving(self):
        """LD-203 leg via the lead-scanner giving tool (per spec slice). The P6
        member rollup rides along on every run."""
        tool = REPO / "skills" / "lead-scanner" / "scripts" / "lda_ld203_giving.py"
        for sl in self.spec.get("giving", []):
            roster = REPO / sl["roster"]
            if not roster.exists():
                self.fail(f"giving: roster missing {roster}")
                continue
            cmd = [sys.executable, str(tool), "--db", str(self.db_path), "--json",
                   "--names-file", str(roster)] + sl.get("args", [])
            print(f"[giving] {' '.join(Path(c).name if os.sep in str(c) else str(c) for c in cmd[1:])}")
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               cwd=str(REPO))
            if r.returncode != 0:
                self.fail(f"giving tool failed for {sl['roster']}: {r.stderr[-500:]}")
                continue
            txt = r.stdout
            res = json.loads(txt[txt.find("{"):])["results"]
            files = sl["files"]
            per = sorted(res.get("per_entity", []),
                         key=lambda e: (-(e["total"] or 0), e["registrant_name"]))
            if sl.get("note_filings_col"):
                by_upper = {r0[0].upper(): r0[2] for r0 in self.rows[f"{self.p}_players.csv"]}
                self.wcsv(files["by_org"],
                          ["ld203_filer_org", "disclosed_giving_total", "items",
                           f"{self.tok}_filings_senate_note"],
                          [[e["registrant_name"], e["total"], e["items"],
                            by_upper.get(e["registrant_name"].upper(), "")] for e in per])
            else:
                self.wcsv(files["by_org"],
                          ["ld203_filer_org", "disclosed_giving_total", "items"],
                          [[e["registrant_name"], e["total"], e["items"]] for e in per])
            rec = sorted(res.get("recipients", []),
                         key=lambda x: (-(x["total"] or 0), x["recipient"]))
            self.wcsv(files["recipients"], ["recipient_raw", "items", "total"],
                      [[x["recipient"], x["items"], x["total"]] for x in rec])
            self.wcsv(files["by_year"], ["filing_year", "total"],
                      [[x["filing_year"], x["total"]] for x in res.get("by_year", [])])
            ru = res.get("member_rollup")
            if ru and files.get("member_rollup"):
                self.wcsv(files["member_rollup"],
                          ["member", "bioguide_id", "chamber", "state", "party_bracket",
                           "direct", "campaign_committee", "leadership_pac",
                           "total_attributable", "jfc_shared_unallocated",
                           "multi_honoree_unallocated", "items", "n_filed_variants",
                           "inferred_flag"],
                          [[m["name"], m["bioguide_id"], m["chamber"], m["state"],
                            m["party_bracket"], m["direct"], m["campaign-committee"],
                            m["leadership-pac"], m["total_attributable"], m["jfc"],
                            m["multi"], m["items"], len(m["variants"]),
                            "inferred" if m["inferred"] else ""] for m in ru["members"]])
            # internal consistency gate: by_year must sum to the deduped total
            tot = res["totals"]["total"] or 0
            ysum = sum(x["total"] or 0 for x in res.get("by_year", []))
            if abs(ysum - tot) > 1:
                self.fail(f"giving {sl['roster']}: by_year sum {ysum} != total {tot}")
            sl["_totals"] = res["totals"]
        self.gate("giving reconciliation")

    # ---------------------------------------------------------------- fec
    def run_fec(self):
        cfg = self.spec.get("modules", {}).get("fec")
        if not cfg:
            return
        files = cfg["files"]
        if cfg.get("mode", "run") == "run":
            tool = REPO / "skills" / "lead-scanner" / "scripts" / "fec_enrich.py"
            roster = REPO / cfg["roster"]
            cmd = [sys.executable, str(tool), "--names-file", str(roster), "--json"] \
                + cfg.get("args", [])
            print("[fec] fec_enrich.py --json (cache-backed; key from env, never stored)")
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               cwd=str(REPO))
            if r.returncode == 0:
                try:
                    f = json.loads(r.stdout[r.stdout.find("{"):])
                    self._fec_csvs(f, files)
                    return
                except Exception as e:
                    print(f"  [fec] parse failed ({e}) — falling back to passthrough")
            else:
                print(f"  [fec] tool failed — falling back to passthrough: {r.stderr[-300:]}")
        # passthrough from the baseline package (cached-API-derived CSVs)
        for name in files.values():
            self._passthrough_one(name, why="FEC (external API; regenerate with "
                                  "fec_enrich.py --names-file <roster> --json, key in env)")

    def _fec_csvs(self, f, files):
        def sjoin(items, n=4):
            outp = []
            for it in items[:n]:
                if isinstance(it, dict):
                    outp.append(str(it.get("name") or it.get("fec_name") or it.get("player") or json.dumps(it)))
                else:
                    outp.append(str(it))
            return "; ".join(outp)
        recon = f.get("reconciliation", [])
        self.wcsv(files["recon"],
                  ["player", "match_confidence", "fec_superpac_contributions", "fec_items",
                   "ld203_disclosed_giving", "delta_fec_minus_ld203", "fec_contributor_names",
                   "committees", "sample_transaction_ids"],
                  [[r["player"], r["confidence"], r["fec_superpac"], r["fec_items"], r["ld203"],
                    r["delta"], sjoin(r.get("fec_names", [])), sjoin(r.get("committees", []), 5),
                    sjoin(r.get("tids", []))] for r in recon])
        self.wcsv(files["unmatched"], ["fec_contributor_name", "total", "items"],
                  [[r["name"], r["total"], r["items"]] for r in f.get("unmatched_network_donors", [])])
        self.wcsv(files["committees"], ["committee_id", "name", "type", "cycles"],
                  [[c["committee_id"], c["name"], c.get("committee_type_full", ""),
                    "; ".join(map(str, c.get("cycles", [])))] for c in f.get("committees", [])])

    # -------------------------------------------------------- passthrough
    def _passthrough_one(self, name, why=""):
        src = self.baseline_root / self.id / "data" / name
        dst = self.data_dir / name
        if src.resolve() == dst.resolve():
            if dst.exists():
                print(f"[keep] {name} (in place{'; ' + why if why else ''})")
                return
        if src.exists():
            shutil.copyfile(src, dst)
            print(f"[passthrough] {name} <- baseline{'; ' + why if why else ''}")
        else:
            print(f"  [warn] passthrough source missing: {name}")

    def run_passthrough(self):
        for name in self.spec.get("passthrough", []):
            self._passthrough_one(name)

    # -------------------------------------------------------- dashboard
    def build_dashboard(self):
        if self.spec.get("assembly") == "viz_build":
            env = dict(os.environ,
                       PKG_PACKAGES_ROOT=str(self.out_root),
                       PKG_GENDATE=self.gendate)
            vb = REPO / "out" / "packages" / "_build" / "viz_build.py"
            r = subprocess.run([sys.executable, str(vb), self.id], env=env,
                               capture_output=True, text=True, encoding="utf-8",
                               cwd=str(REPO))
            print(r.stdout[-2000:])
            if r.returncode != 0:
                self.fail(f"viz_build assembly failed: {r.stderr[-800:]}")
                self.gate("dashboard assembly")
            return
        if self.lens["type"] == "issue_codes":
            data, default_page = self.assemble_codes(), "codes_page.js"
        else:
            data, default_page = self.assemble_facet(), "facet_page.js"
        tpl = (VIZ / "template.html").read_text(encoding="utf-8")
        html = (tpl.replace("__TITLE__", self.spec["title"])
                .replace("__SUBTITLE__", self.spec["subtitle"])
                .replace("__GENDATE__", self.gendate)
                .replace("__EXTRA_SOURCES__", self.spec.get("extra_sources", ""))
                .replace("__CSS__", (VIZ / "shared.css").read_text(encoding="utf-8"))
                .replace("__LIB__", (VIZ / "lib.js").read_text(encoding="utf-8"))
                .replace("__DATA__", json.dumps(data, ensure_ascii=False))
                .replace("__PAGE__", (VIZ / self.spec.get("page_js", default_page))
                         .read_text(encoding="utf-8")))
        out = self.pkg_dir / f"{self.id}_dashboard.html"
        out.write_text(html, encoding="utf-8")
        print(f"[html] {out} ({len(html)//1024} KB)")

    def assemble_facet(self):
        sp = self.spec
        classes = sp.get("classes")
        players = []
        pcols = self.cols[f"{self.p}_players.csv"]
        idx = {c: i for i, c in enumerate(pcols)}
        shorts = {k.upper(): v for k, v in sp.get("copy", {}).get("shorts", {}).items()}
        for r in self.rows[f"{self.p}_players.csv"]:
            cls_idx = 0
            note = ""
            if classes and "client_class" in idx:
                cls_idx = classes["map"].get(r[idx["client_class"]], len(classes["names"]) - 1)
                note = r[idx["class_note"]] if "class_note" in idx else ""
            players.append({"name": r[0], "short": shorten(tcase(r[0]) or r[0], shorts),
                            "filings": r[idx[f"{self.tok}_filings_senate"]],
                            "spend": r[idx["total_all_issue_spend"]],
                            "cls": cls_idx, "note": note,
                            "y0": str(r[idx["first_year"]]), "y1": str(r[idx["last_year"]])})
        player_filings = {}
        for r in self.rows[f"{self.p}_player_filings.csv"]:
            lab = f"{r[2]} {PQ2.get(r[3], r[3])} ({r[4]})"
            player_filings.setdefault(r[0], []).append(
                [r[8], lab, tcase(r[5]) or r[5], r[6],
                 1 if str(r[4]).startswith("R") else 0, r[7] or ""])
        QN = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "MY": 5, "YE": 6}
        for lst in player_filings.values():
            lst.sort(key=lambda f: (f[1][:4], QN.get(f[1][5:7], 9), f[2]))
        trows = self.rows[f"{self.p}_quarterly_trend.csv"]
        tcols = {c: i for i, c in enumerate(self.cols[f"{self.p}_quarterly_trend.csv"])}
        scol = self.lens.get("spend_col", "canonical_spend_tagged_clients")
        trend = {"q": [q_label(r[0], r[1]) for r in trows],
                 "filings": [r[tcols[f"{self.tok}_filings"]] for r in trows],
                 "clients": [r[tcols[f"{self.tok}_clients"]] for r in trows]}
        if scol in tcols:
            trend["spend"] = [r[tcols[scol]] for r in trows]
        trend_filings = {}
        for r in self.rows[f"{self.p}_trend_filings.csv"]:
            trend_filings.setdefault(q_label(r[0], r[1]), []).append(
                [r[7], r[2], tcase(r[3]) or r[3], r[4], r[6] or ""])
        scatter = [{"code": r[0], "name": CODE_NAMES.get(r[0], ""),
                    "docs": r[1], "pct": r[2]}
                   for r in self.rows[f"{self.p}_issue_code_scatter.csv"][:14]]
        keywords = [{"kw": r[0], "filings": r[1]} for r in self.rows[f"{self.p}_keywords.csv"]]
        registrants = [{"name": tcase(r[0]) or r[0], "filings": r[1], "clients": r[2],
                        "amt": r[3]} for r in self.rows[f"{self.p}_registrant_firms.csv"]]
        prows = self.rows[f"{self.p}_press_quarterly.csv"]
        press = {"q": [r[0] for r in prows], "all": [r[1] for r in prows],
                 "n": [r[2] for r in prows], "share": [float(r[3]) for r in prows]}
        PARTY_L = {"Democrat": "D", "Republican": "R", "Independent": "I"}
        press_releases = {}
        for r in self.rows[f"{self.p}_press_releases.csv"]:
            press_releases.setdefault(r[0], []).append(
                [r[1], r[2], PARTY_L.get(r[3], (r[3] or "?")[:1]), r[4],
                 (r[6] or "")[:110], r[7]])
        data = {"kpis": sp["kpis"], "players": players, "playerFilings": player_filings,
                "trend": trend, "trendFilings": trend_filings, "scatter": scatter,
                "keywords": keywords, "registrants": registrants, "press": press,
                "pressReleases": press_releases, "caveats": sp["caveats"],
                "findings": sp.get("findings", []),
                "copy": sp.get("copy", {}),
                "classes": classes["names"] if classes else None,
                "classSlots": classes.get("slots") if classes else None}
        ename = f"{self.p}_engagements.csv"
        if ename in self.rows:
            ecols = {c: i for i, c in enumerate(self.cols[ename])}
            data["engagements"] = [
                {"player": e[0], "reg": tcase(e[1]) or e[1], "q0": e[2], "q1": e[3],
                 "nq": e[4], "total": e[5], "term": e[6] == "yes", "termQ": e[7],
                 "cls": e[ecols["client_class"]],
                 "text": (e[ecols["declared_text_sample"]] or "")[:220], "uuid": e[8]}
                for e in self.rows[ename]]
        giving = self.giving_widget()
        if giving:
            data["giving"] = giving
        data["queryInfo"] = self.query_info()
        return data

    def giving_widget(self):
        """Shared giving-widget data (facet + issue_codes lens): the first
        spec giving slice marked chart:true, or None. Same shape both lenses."""
        for sl in self.spec.get("giving", []):
            if not sl.get("chart"):
                continue
            files = sl["files"]
            g = {
                "orgs": [{"name": tcase(r[0]) or r[0], "total": r[1], "items": r[2]}
                         for r in self.rows.get(files["by_org"], [])[:12]],
                "recipients": [{"name": r[0], "total": r[2], "items": r[1]}
                               for r in self.rows.get(files["recipients"], [])[:12]],
                "total": (sl.get("_totals") or {}).get("total")}
            if files.get("member_rollup") and files["member_rollup"] in self.rows:
                g["members"] = [
                    {"name": ("Sen. " if m[2] == "Senate" else "Rep. ") + m[0] + " " + m[4],
                     "total": m[8], "direct": m[5], "campaign": m[6], "ldpac": m[7],
                     "jfc": m[9], "multi": m[10], "inferred": bool(m[13])}
                    for m in self.rows[files["member_rollup"]][:12]]
            return g
        return None

    def assemble_codes(self):
        """Data assembly for the generic issue_codes-lens dashboard (codes_page.js).
        Mirrors assemble_facet()'s shape where the underlying CSVs allow it, but
        this lens's exporter (run()) never produces most of the per-filing
        click-through indices (player_filings/trend_filings) the way the facet
        lens or the legacy viz_build healthcare build do — so those widgets stay
        reconciled aggregate charts + table views only (the same no-click-through
        precedent as the facet page's registrants/keywords/giving widgets, which
        also lack it). Press IS an exception: x_press_releases_codes() produces
        a per-filing index the same way the facet lens's press widget does, so
        the press-coupling chart clicks through to the actual releases."""
        sp = self.spec
        pcols = self.cols[f"{self.p}_players.csv"]
        idx = {c: i for i, c in enumerate(pcols)}
        shorts = {k.upper(): v for k, v in sp.get("copy", {}).get("shorts", {}).items()}
        share_col = f"{self.tok}_activity_share_pct"
        players = []
        for r in self.rows[f"{self.p}_players.csv"]:
            players.append({
                "name": r[0], "short": shorten(tcase(r[0]) or r[0], shorts),
                "filings": r[idx[f"{self.tok}_filings"]],
                "sharePct": float(r[idx[share_col]]) if share_col in idx and r[idx[share_col]] is not None else None,
                "spend": r[idx["total_all_issue_spend"]],
                "y0": str(r[idx["first_year"]]), "y1": str(r[idx["last_year"]])})
        # scatter selection: top-150-by-filings ∪ top-30-by-spend, so the chart
        # stays legible at this lens's scale (thousands of players) while the
        # table view below stays the FULL, unfiltered roster
        by_filings = {p["name"] for p in sorted(players, key=lambda p: -p["filings"])[:150]}
        by_spend = {p["name"] for p in sorted([p for p in players if p["spend"]], key=lambda p: -p["spend"])[:30]}
        sel = by_filings | by_spend
        for p in players:
            p["inScatter"] = p["name"] in sel
        trows = self.rows[f"{self.p}_quarterly_trend.csv"]
        tcols_ = {c: i for i, c in enumerate(self.cols[f"{self.p}_quarterly_trend.csv"])}
        scol = self.lens.get("spend_col", "canonical_spend_tagged_clients")
        trend = {"q": [q_label(r[0], r[1]) for r in trows],
                 "filings": [r[tcols_[f"{self.tok}_filings"]] for r in trows],
                 "clients": [r[tcols_[f"{self.tok}_clients"]] for r in trows]}
        if scol in tcols_:
            trend["spend"] = [r[tcols_[scol]] for r in trows]
        ct = {}
        for r in self.rows.get(f"{self.p}_code_trend.csv", []):
            ct.setdefault(q_label(r[0], r[1]), {})[r[2]] = r[3]
        qs = trend["q"]
        code_trend = {"q": qs, "series": [
            {"code": c, "name": CODE_NAMES.get(c, c), "values": [ct.get(q, {}).get(c, 0) for q in qs]}
            for c in self.codes]}
        registrants = [{"name": tcase(r[0]) or r[0], "filings": r[1], "clients": r[2], "amt": r[3]}
                       for r in self.rows[f"{self.p}_registrant_firms.csv"]]
        bills = [{"bill": r[0], "clients": r[1], "filings": r[2], "y0": r[3], "y1": r[4]}
                 for r in self.rows.get(f"{self.p}_bills.csv", [])]
        prows = self.rows[f"{self.p}_press_coupling.csv"]
        pcols2 = {c: i for i, c in enumerate(self.cols[f"{self.p}_press_coupling.csv"])}
        tok_press = sp["press"].get("col_token", self.tok)
        press = {"q": [r[0] for r in prows],
                 "all": [r[pcols2["all_releases"]] for r in prows],
                 "n": [r[pcols2[f"{tok_press}_releases"]] for r in prows],
                 "share": [float(r[pcols2[f"{tok_press}_press_share_pct"]]) for r in prows]}
        scol2 = self.lens.get("spend_col", f"canonical_spend_{self.p}_clients")
        if scol2 in pcols2:
            press["spend"] = [r[pcols2[scol2]] for r in prows]
        PARTY_L = {"Democrat": "D", "Republican": "R", "Independent": "I"}
        press_releases = {}
        for r in self.rows.get(f"{self.p}_press_releases.csv", []):
            press_releases.setdefault(r[0], []).append(
                [r[1], r[2], PARTY_L.get(r[3], (r[3] or "?")[:1]), r[4],
                 (r[6] or "")[:110], r[7]])
        data = {"kpis": sp["kpis"], "players": players, "trend": trend, "codeTrend": code_trend,
                "registrants": registrants, "bills": bills, "press": press,
                "pressReleases": press_releases,
                "caveats": sp["caveats"], "findings": sp.get("findings", []),
                "copy": sp.get("copy", {})}
        giving = self.giving_widget()
        if giving:
            data["giving"] = giving
        data["queryInfo"] = self.query_info_codes()
        return data

    def query_info(self):
        dbnote = (f"DB: db/{self.db_path.name} (read-only). Rebuild: lda-corpus-loader/build_db.py → "
                  f"lda-entity-resolver/resolve_entities.py"
                  + (" → lead-scanner/lda_industry_map.py --build-tags" if self.lens["type"] == "facet" else "")
                  + ". Generated by skills/industry-review-packager/scripts/lda_package_industry.py "
                  f"specs/{self.id}.json — the SQL shown is the exact string the generator executed.")

        def qi(title, note, *names):
            return {"title": title, "note": note + " " + dbnote,
                    "blocks": [{"label": f"SQL → data/{n}", "text": self.sql_log[n]}
                               for n in names if n in self.sql_log]}
        p = self.p
        out = {
            "kpis": qi("Header stats — where each number comes from",
                       "KPI values are human-written copy carried by the package spec; "
                       "reconcile each against the named CSV after a regeneration.",
                       f"{p}_quarterly_trend.csv"),
            "players": qi("Player map — the queries behind it",
                          f"CLICK-THROUGH: click a bubble to list its raw filings "
                          f"(full index: data/{p}_player_filings.csv, one lda.senate.gov URL per filing; "
                          f"counts reconcile with the map at build time — a mismatch fails the build).",
                          f"{p}_players.csv", f"{p}_player_filings.csv"),
            "trend": qi("Quarterly trend — the query behind it",
                        f"CLICK-THROUGH: click a quarter to list exactly the deduped filings it counts "
                        f"(data/{p}_trend_filings.csv — reconciled at build time). Amendments deduped on "
                        "(registrant_id, client_id, filing_year, filing_period) latest-by-posted; "
                        "registrations (R*) excluded.",
                        f"{p}_quarterly_trend.csv", f"{p}_trend_filings.csv"),
            "scatter": qi("Issue-code scatter — the query behind it",
                          "Tagged free-text blocks grouped by the ALI issue code the registrant "
                          "filed them under.", f"{p}_issue_code_scatter.csv"),
            "keywords": qi("Vocabulary — the query behind it",
                           "Distinct filings per curated lexicon phrase (whole-word matches recorded "
                           "in lobbying_issue_mentions). Discovery proposes; only human-curated "
                           "phrases in industry_lexicon.json tag.", f"{p}_keywords.csv"),
            "registrants": qi("Registrant firms — the query behind it",
                              "Outside firms only (registrant ≠ client), amendment-deduped; reported "
                              "amounts are ranking signals.", f"{p}_registrant_firms.csv"),
            "press": qi("Press share — the query behind it",
                        f"CLICK-THROUGH: click a quarter to list the matching releases "
                        f"(data/{p}_press_releases.csv, src_file:src_line citation keys — counts "
                        "reconciled at build time). Whole-word regex over member releases (title + text).",
                        f"{p}_press_quarterly.csv", f"{p}_press_releases.csv"),
        }
        if f"{p}_engagements.csv" in self.sql_log:
            out["engagements"] = qi(
                "Engagements — the query behind them",
                "Engagement grain = (registrant, client) pair among tagged filings; a quarter counts "
                "as tagged if ANY amendment version was tagged; dollars from the deduped survivor; "
                "termination from the DECLARED filing_type family ^[1-4](T|TY|@|@Y)$ — never inferred.",
                f"{p}_engagements.csv")
        if self.spec.get("giving"):
            out["giving"] = self._giving_query_info(dbnote)
        return out

    def _giving_query_info(self, dbnote):
        return {"title": "LD-203 giving — how these numbers are produced",
                "note": ("Produced by a tool run, not one SQL: "
                         "skills/lead-scanner/scripts/lda_ld203_giving.py --json "
                         "--names-file <roster> (amendment-deduped on the full contribution "
                         "identity; member rollup via the P6 member_resolve layer — rollup, "
                         "never conflation; JFC/multi-honoree dollars stay shared/unallocated). "
                         "Citeable SQL blocks: queries/ld203_giving.sql G1a–G1d. LD-203 is "
                         "registrant-filed and is NOT FEC — say 'disclosed LD-203 giving', "
                         "never 'total'. ") + dbnote,
                "blocks": []}

    def query_info_codes(self):
        """query_info() counterpart for the issue_codes-lens dashboard: cites
        this lens's own CSVs (no player_filings/trend_filings — this lens's
        exporter never produces those per-filing click-through indices, so
        those widgets claim none). Press is the exception: press_releases IS
        produced here (x_press_releases_codes()), so the press widget clicks
        through same as the facet lens."""
        dbnote = (f"DB: db/{self.db_path.name} (read-only). Rebuild: lda-corpus-loader/build_db.py → "
                  f"lda-entity-resolver/resolve_entities.py. Generated by "
                  f"skills/industry-review-packager/scripts/lda_package_industry.py specs/{self.id}.json "
                  f"— the SQL shown is the exact string the generator executed.")

        def qi(title, note, *names):
            return {"title": title, "note": note + " " + dbnote,
                    "blocks": [{"label": f"SQL → data/{n}", "text": self.sql_log[n]}
                               for n in names if n in self.sql_log]}
        p = self.p
        out = {
            "kpis": qi("Header stats — where each number comes from",
                       "KPI values are human-written copy carried by the package spec; "
                       "reconcile each against the named CSVs after a regeneration.",
                       f"{p}_quarterly_trend.csv"),
            "players": qi("Player map — the query behind it",
                          "No per-filing click-through in this generic codes-lens page (unlike "
                          "facet-lens or the legacy bespoke healthcare/crypto dashboards) — every "
                          "player's tagged-filing count, activity share, and spend is exact and "
                          f"reconciled at build time. Full roster: data/{p}_players.csv.",
                          f"{p}_players.csv"),
            "trend": qi("Quarterly trend — the query behind it",
                        "Amendment-deduped on (registrant_id, client_id, filing_year, filing_period) "
                        "latest-by-posted; registrations (R*) excluded.",
                        f"{p}_quarterly_trend.csv"),
            "codeTrend": qi("Per-code trend — the query behind it",
                            "Tagged filings per quarter per ALI issue code (a filing naming more than "
                            "one of the spec'd codes counts once per code, so code totals can exceed "
                            "the trend chart's per-quarter filing count).",
                            f"{p}_code_trend.csv"),
            "registrants": qi("Registrant firms — the query behind it",
                              "Outside firms only (registrant ≠ client), amendment-deduped; reported "
                              "amounts are ranking signals.", f"{p}_registrant_firms.csv"),
            "bills": qi("Bills — the query behind it",
                        "Bills named in tagged filings' free-text, ranked by distinct clients.",
                        f"{p}_bills.csv"),
            "press": qi("Press coupling — the query behind it",
                        f"CLICK-THROUGH: click a quarter to list the matching releases "
                        f"(data/{p}_press_releases.csv, src_file:src_line citation keys — counts "
                        "reconciled at build time). Share of ALL member press releases tagged (via "
                        "press_issue_mentions, the curated ISSUE_KEYWORDS dict in build_db.py) to "
                        "the spec'd codes, alongside canonical spend of tagged clients, by quarter. "
                        "Some codes may have thin or no press vocabulary — check the package caveats.",
                        f"{p}_press_coupling.csv", f"{p}_press_releases.csv"),
        }
        if self.spec.get("giving"):
            out["giving"] = self._giving_query_info(dbnote)
        return out

    # ------------------------------------------------------------ readme
    def write_readme(self):
        cfg = self.spec.get("readme", {})
        path = self.pkg_dir / "README.md"
        if not cfg.get("write"):
            print("[readme] spec says keep the curated README (write: false)")
            return
        if path.exists() and not self.args.force_readme:
            print("[readme] exists — left untouched (use --force-readme to regenerate)")
            return
        lens_line = (f"filings whose free-text matches the curated `{self.tag}` vocabulary "
                     f"(industry_lexicon.json)" if self.lens["type"] == "facet"
                     else f"filings whose senate activities carry issue codes {', '.join(self.codes)}")
        L = [f"# {self.spec['title']}", "",
             f"*Generated {self.gendate} · unverified research output for team review.*", "",
             self.spec["subtitle"], ""]
        for para in cfg.get("overview", []):
            L += [para, ""]
        L += ["## What is in scope", "",
              f"Scope = {lens_line}. Senate filings are primary; House versions of the same "
              "filings are never added on top (they are copies). Filings are amendment-deduplicated "
              "on (registrant, client, year, quarter) keeping the latest by posting date; "
              "registrations are excluded from dollar work. Client spend comes only from the "
              "double-count-corrected canonical spend view.", "",
              "## Files", "",
              "| file | rows | what it is |", "|---|---|---|"]
        notes = cfg.get("file_notes", {})
        for name in sorted(self.rows):
            L.append(f"| data/{name} | {len(self.rows[name])} | {notes.get(name, '')} |")
        L += ["", "## Caveats that matter", ""]
        for c in self.spec["caveats"]:
            L.append(f"- {c}")
        has_dashboard = (self.pkg_dir / f"{self.id}_dashboard.html").exists()
        # the generic issue_codes-lens dashboard (assemble_codes/codes_page.js) has full
        # click-through only on its press widget (x_press_releases_codes()); facet-lens
        # and legacy viz_build dashboards click through on every widget that has one.
        has_click_through = has_dashboard and (self.spec.get("assembly") == "viz_build"
                                                or self.lens["type"] == "facet")
        has_press_click_through = has_dashboard and self.lens["type"] == "issue_codes"
        L += ["", "## How to QA a number", "", (
              "1. Every chart is click-through to the raw filings behind it; every filing links "
              "to its public record on lda.senate.gov; press rows carry `src_file:src_line` keys."
              if has_click_through else
              "1. This package's dashboard's press-coupling widget clicks through to the "
              "individual matching releases (with links); the other widgets (players, trend, "
              "registrants) are reconciled aggregate charts + full table views only, without "
              "per-filing click-through. Every CSV row still carries a citation key — senate "
              "`filing_uuid`, press `src_file:src_line` — resolvable via show_record.py."
              if has_press_click_through else
              "1. This package's dashboard has no per-filing click-through (data-only for "
              "the underlying records). Every CSV row still carries a citation key — senate "
              "`filing_uuid`, press `src_file:src_line` — resolvable via show_record.py."
              if has_dashboard else
              "1. No interactive dashboard ships in this release (data-only build). Every CSV row "
              "still carries a citation key — senate `filing_uuid`, press `src_file:src_line` — "
              "resolvable via show_record.py."),
              "2. Chart-vs-list reconciliation ran at build time and a mismatch fails the build "
              "(trend counts, per-player filing counts, press counts" +
              (", spend sums" if self.spec.get("modules", {}).get("spend_quarters") else "") + ").", (
              "3. The SQL behind each widget is embedded in the dashboard (hover ⋯ → View query info) "
              "— it is the exact string the generator executed."
              if has_dashboard else
              "3. The exact SQL behind each CSV is in this script's export functions "
              "(skills/industry-review-packager/scripts/lda_package_industry.py) — no dashboard "
              "means no embedded query-info viewer for this package."), "",
              "## Regenerate", "",
              "```", f"python skills/industry-review-packager/scripts/lda_package_industry.py \\",
              f"    skills/industry-review-packager/specs/{self.id}.json", "```", ""]
        for para in cfg.get("notes", []):
            L += [para, ""]
        path.write_text("\n".join(L), encoding="utf-8")
        print(f"[readme] {path}")

    # ------------------------------------------------------- render check
    def render_check(self):
        html = self.pkg_dir / f"{self.id}_dashboard.html"
        if not html.exists():
            self.fail("render: dashboard HTML missing")
            self.gate("render check")
        edge = None
        for c in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
            if os.path.exists(c):
                edge = c
                break
        if not edge:
            print("  [warn] msedge not found — render check SKIPPED")
            return
        tmp = self.pkg_dir / "_render_check"
        tmp.mkdir(exist_ok=True)
        # onerror probe: a JS exception mid-page leaves the KPI row rendered and a
        # plausible-size screenshot, so screenshot size alone is NOT a render check
        # (that exact failure happened on this skill's first build). The probe puts
        # any error into document.title, which --dump-dom exposes.
        probe = ("<script>window.onerror=function(m,s,l,c){document.title="
                 "'RENDER_ERR: '+m+' @'+l+':'+c;return false};</script>")
        try:
            src = html.read_text(encoding="utf-8").replace(
                '<body class="viz-root">', '<body class="viz-root">' + probe, 1)
            for theme in ("light", "dark"):
                page = tmp / f"{theme}.html"
                page.write_text(src.replace('<html lang="en">',
                                            f'<html lang="en" data-theme="{theme}">', 1),
                                encoding="utf-8")
                png = tmp / f"{theme}.png"
                r = subprocess.run([edge, "--headless=new", "--disable-gpu",
                                    f"--screenshot={png}", "--window-size=1400,2400",
                                    "--virtual-time-budget=8000", page.as_uri()],
                                   capture_output=True, timeout=120)
                dom = subprocess.run([edge, "--headless=new", "--disable-gpu",
                                      "--dump-dom", "--virtual-time-budget=8000",
                                      page.as_uri()],
                                     capture_output=True, timeout=120)
                m = re.search(r"<title>(RENDER_ERR:[^<]*)", dom.stdout.decode("utf-8", "replace"))
                if m:
                    self.fail(f"render {theme}: page JS threw — {m.group(1)[:200]}")
                elif not png.exists() or png.stat().st_size < 20000:
                    self.fail(f"render: {theme} screenshot missing/blank "
                              f"({png.stat().st_size if png.exists() else 0} bytes)")
                else:
                    print(f"[render] {theme}: OK ({png.stat().st_size//1024} KB screenshot, no JS errors)")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.gate("render check")

    # ---------------------------------------------------------------- zip
    def write_zip(self):
        if not self.spec.get("zip", True):
            return
        zp = self.pkg_dir / f"{self.id}_package_{self.gendate}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in (f"{self.id}_dashboard.html", "README.md", "DATA_DICTIONARY.md"):
                p = self.pkg_dir / f
                if p.exists():
                    z.write(p, f)
            for p in sorted(self.data_dir.glob("*.csv")):
                z.write(p, f"data/{p.name}")
        print(f"[zip] {zp} ({zp.stat().st_size//1024} KB)")

    # --------------------------------------------------------------- run
    def run(self):
        m = self.spec.get("modules", {})
        print(f"=== industry-review-packager · {self.id} · lens={self.lens['type']} "
              f"· out={self.pkg_dir} ===")
        self.x_players()
        if self.lens["type"] == "facet":
            self.x_player_filings()
            self.x_trend()
            self.x_trend_filings()
            self.x_scatter()
            if m.get("scatter_filings"):
                self.x_scatter_filings()
            self.x_keywords()
            self.x_registrants()
            self.x_press()
            self.x_press_releases()
            self.x_samples()
            if m.get("engagements"):
                self.x_engagements()
            if m.get("spend_quarters"):
                self.x_spend_quarters()
            if m.get("bills"):
                self.x_bills()
        else:
            self.x_trend()
            self.x_code_trend()
            self.x_registrants()
            if m.get("bills"):
                self.x_bills()
            self.x_press_coupling()
            self.x_press_releases_codes()
            self.x_samples()
        self.x_roster()
        if not self.args.skip_giving:
            self.run_giving()
        self.run_fec()
        self.run_passthrough()
        if not self.args.skip_dashboard:
            self.build_dashboard()
        self.write_readme()
        if not (self.args.skip_render or self.args.skip_dashboard):
            self.render_check()
        if not self.args.skip_zip:
            self.write_zip()
        self.gate("final")
        print(f"\nDONE — {self.id} package at {self.pkg_dir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="path to specs/<pkg>.json")
    ap.add_argument("--db", default=None, help="DuckDB path (default db/lda_full.duckdb)")
    ap.add_argument("--out-root", default=None,
                    help="packages root to write into (default out/packages; point at a "
                         "scratch dir for a regression regeneration)")
    ap.add_argument("--baseline-root", default=None,
                    help="packages root passthrough files are copied FROM (default out/packages)")
    ap.add_argument("--gendate", default=None, help="generation date label (default today)")
    ap.add_argument("--skip-giving", action="store_true")
    ap.add_argument("--skip-dashboard", action="store_true")
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--skip-zip", action="store_true")
    ap.add_argument("--force-readme", action="store_true")
    args = ap.parse_args()
    Packager(args.spec, args.db, args.out_root, args.baseline_root,
             args.gendate, args).run()


if __name__ == "__main__":
    main()
