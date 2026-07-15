#!/usr/bin/env python3
"""Build the GAIN investigation database from the raw challenge corpus.

Parses three datasets (layout per the challenge data manual) into one DuckDB file:

  <data-root>/congress_press/   JSONL press releases (year dirs + 2026 files at root)
  <data-root>/senate/           Senate LDA filings + contributions (JSON arrays, streamed)
  <data-root>/house/            House LDA registrations + quarterlies (one XML per filing)

Guarantees:
  * Every row carries a raw-record pointer (src_file + src_line/src_index, or the XML
    path) so any query result resolves to a citable raw record in one step
    (see show_record.py).
  * A sanity report reconciles row counts against the data manual's published 2025
    scale before the database is trusted. Written next to the DB as sanity_report.md.

Usage:
  python build_db.py --data-root data/                       # everything present
  python build_db.py --data-root data/ --years 2025 2026     # pilot slice
  python build_db.py --data-root data/ --sample 2025-Q1      # smoke mode (minutes)

Caveat: Senate JSON key names and House XML tag names were drafted from the data
manual before the raw data landed and are coded defensively (multiple candidate
keys/tags, strip everything). The sanity report is the tripwire for mismatches —
verify against real data before trusting downstream queries.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb
import ijson

BATCH = 50000

# Sanity report contains non-ASCII; Windows pipes default to cp1252.
# line_buffering so phase progress reaches a redirected log as it happens
# (block buffering otherwise holds every print until process exit).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# Data manual's published 2025 scale, used by the sanity report.
MANUAL_2025 = {
    "press_releases": 48000,        # "~48K releases in 2025"
    "senate_filings": 108225,
    "senate_contributions": 39438,
    "house_filings": 108522,        # ~7,762 registrations + ~100,760 quarterlies
}

# Bill citations: longest alternatives first so "H.J.Res." doesn't match as "H.R.".
BILL_RE = re.compile(
    r"\b("
    r"H\.?\s*J\.?\s*RES\.?|S\.?\s*J\.?\s*RES\.?|"
    r"H\.?\s*CON\.?\s*RES\.?|S\.?\s*CON\.?\s*RES\.?|"
    r"H\.?\s*RES\.?|S\.?\s*RES\.?|"
    r"H\.?\s*R\.?|S\.?"
    r")\s*(\d{1,5})\b",
    re.IGNORECASE,
)


def norm_bill(prefix: str, number: str) -> str:
    return re.sub(r"[^A-Z]", "", prefix.upper()) + number


def extract_bills(text):
    if not text:
        return
    for m in BILL_RE.finditer(text):
        yield norm_bill(m.group(1), m.group(2)), m.group(0)


# ---------------------------------------------------------- press issue tagging
#
# Tags press-release text with ALI issue codes (data/senate/constants/
# lobbying_activity_issues.json) using a curated keyword vocabulary, so press
# volume on an issue can be compared to lobbying spend on the same code
# (v_spend_by_issue_quarter). This is the press-side analogue of extract_bills:
# one raw-record-pointer'd row per (issue_code, keyword) that appears in a release.
#
# DESIGN / PROVENANCE OF THE MAPPING (read before trusting any downstream count):
#   * Precision over recall. Keywords are distinctive phrases, not bare topic words
#     ("border security" not "border"; "national defense" not "defense"), matched
#     on whole-word boundaries, case-insensitively, with flexible interior
#     whitespace (so "health\ncare" across a line break still matches "health care").
#   * Each keyword string maps to exactly ONE code (asserted at build time), so a
#     hit is unambiguously attributable. Where a concept could belong to two codes,
#     it is assigned to the closest ALI code and flagged in SHAKY_MAPPINGS below.
#   * NOT exhaustive over the ~79 ALI codes. It covers the codes congressional
#     press releases actually discuss, with vocabulary specific enough to trust.
#   * A "mention" is deduped per release: one row per (pr_id, issue_code, keyword),
#     never one-per-occurrence, so a release repeating "health care" ten times does
#     not outweigh ten releases mentioning it once. Volume metrics downstream should
#     COUNT(DISTINCT pr_id).
#
# Known ambiguities are recorded here (not hidden) and in the coupling write-up:
SHAKY_MAPPINGS = """
  tariff/tariffs -> TRD (Trade), NOT TAR: ALI's TAR code is narrowly "miscellaneous
    tariff bills"; LDA filers file broad tariff/trade-war policy under TRD, so press
    "tariffs" is mapped to TRD to keep the say-vs-pay join meaningful. Watch this one.
  health cluster HCR/MED/MMM/PHA/ALC bleeds: ACA "tax credits" tag BOTH HCR and TAX;
    "prescription drug" -> PHA but reads as HCR; medicare/medicaid -> MMM; opioid/
    fentanyl -> ALC though often framed as LAW or HCR.
  tech cluster CPI/SCI/TEC: "artificial intelligence" -> SCI, "semiconductor" -> CPI,
    "broadband/spectrum" -> TEC. Real releases blur these; treat the three as one
    loose "tech" bucket when reading trends.
  social security -> RET (no dedicated SS code exists; RET=Retirement is closest;
    it is arguably WEL). federal reserve -> BAN (could be MON). background check ->
    FIR (assumes firearms context; could be employment). insurance premiums are NOT
    mapped to INS (they are overwhelmingly health-context) -> INS is flood/auto/
    property only and is a weak, low-volume code. COM/SPO/GAM/ANI are low-precision
    breadth codes, included but noisy.
"""

# code -> list of distinctive keyword phrases (lowercase, single-spaced).
ISSUE_KEYWORDS = {
    "HCR": ["health care", "healthcare", "affordable care act", "obamacare",
            "health insurance", "health coverage", "health care costs",
            "health care system", "public health", "health care coverage"],
    "MMM": ["medicare", "medicaid", "medicare advantage", "dual eligible"],
    "PHA": ["prescription drug", "prescription drugs", "drug prices", "drug pricing",
            "pharmacy", "pharmacist", "pharmacy benefit", "insulin"],
    "MED": ["medical research", "clinical trial", "clinical trials",
            "disease research", "national institutes of health", "biomedical research"],
    "TAX": ["tax credit", "tax credits", "tax cut", "tax cuts", "tax reform",
            "tax code", "taxation", "internal revenue service", "income tax",
            "corporate tax", "child tax credit", "estate tax"],
    "BUD": ["appropriations", "government shutdown", "debt ceiling", "federal budget",
            "budget deficit", "continuing resolution", "national debt", "debt limit",
            "discretionary spending"],
    "IMM": ["immigration", "immigrant", "immigrants", "border security",
            "southern border", "undocumented", "asylum seekers", "daca",
            "deportation", "border crossing", "illegal immigration"],
    "DEF": ["national defense", "defense department", "department of defense",
            "pentagon", "ndaa", "national defense authorization", "armed forces",
            "military readiness", "defense spending", "servicemembers"],
    "FIR": ["gun violence", "gun control", "gun safety", "firearm", "firearms",
            "second amendment", "assault weapons", "background check",
            "background checks", "ghost guns"],
    "ENG": ["clean energy", "renewable energy", "nuclear power", "energy policy",
            "energy prices", "power grid", "electric grid", "solar energy",
            "wind energy", "energy independence", "energy costs"],
    "ENV": ["climate change", "environmental protection", "greenhouse gas",
            "greenhouse gases", "carbon emissions", "superfund", "air pollution",
            "climate crisis", "environmental protection agency"],
    "CAW": ["clean water", "clean air", "drinking water", "air quality",
            "water quality", "pfas", "safe drinking water"],
    "FUE": ["gas prices", "gasoline prices", "oil and gas", "crude oil",
            "offshore drilling", "natural gas", "fossil fuels"],
    "AGR": ["farm bill", "farmers", "agriculture", "agricultural", "crop insurance",
            "department of agriculture", "livestock"],
    "VET": ["veterans", "veteran", "veterans affairs", "department of veterans affairs",
            "gi bill", "va health care", "veterans benefits"],
    "EDU": ["student loan", "student loans", "student debt", "public schools",
            "higher education", "department of education", "pell grant",
            "pell grants", "k-12", "school funding", "college affordability", "teachers"],
    "LBR": ["labor union", "labor unions", "minimum wage", "workers rights",
            "collective bargaining", "overtime pay", "workplace safety",
            "right to work", "project labor agreement", "antitrust", "unionize"],
    "HOU": ["affordable housing", "homelessness", "public housing", "housing costs",
            "housing affordability", "homeless", "section 8"],
    "RET": ["social security", "retirement savings", "pension", "pensions", "401(k)",
            "retirement security"],
    "CIV": ["civil rights", "voting rights", "civil liberties", "voter suppression",
            "lgbtq", "discrimination"],
    "FAM": ["abortion", "reproductive rights", "pro-life", "pro-choice",
            "paid family leave", "planned parenthood"],
    "POS": ["postal service", "usps", "post office", "postal facilities",
            "letter carriers"],
    "FIN": ["wall street", "securities and exchange", "cryptocurrency", "crypto",
            "stablecoin", "digital assets", "private equity", "hedge fund",
            "stock market", "sec regulation"],
    "BAN": ["banking", "banks", "community banks", "credit union", "credit unions",
            "federal reserve", "bank regulation"],
    "INS": ["flood insurance", "auto insurance", "insurance market", "property insurance"],
    "TEC": ["broadband", "telecommunications", "spectrum", "net neutrality", "5g",
            "rural broadband"],
    "COM": ["broadcasting", "local news", "television stations", "radio stations",
            "cable television"],
    "CPI": ["semiconductor", "semiconductors", "chips act", "data center",
            "data centers", "cloud computing"],
    "SCI": ["artificial intelligence", "ai regulation", "scientific research",
            "research and development", "national science foundation",
            "quantum computing", "stem education"],
    "TRD": ["trade agreement", "free trade", "trade deal", "trade war", "tariff",
            "tariffs", "exports", "imports", "world trade organization",
            "trade policy", "section 301", "trade deficit"],
    "LAW": ["law enforcement", "criminal justice", "violent crime", "police officers",
            "public safety", "sentencing reform", "mass incarceration"],
    "ALC": ["opioid", "opioids", "fentanyl", "drug abuse", "substance abuse",
            "overdose", "opioid crisis", "addiction"],
    "HOM": ["homeland security", "department of homeland security", "tsa",
            "cybersecurity", "cyberattack"],
    "FOR": ["foreign policy", "foreign relations", "foreign aid", "state department",
            "economic sanctions", "human rights abuses"],
    "AVI": ["airline", "airlines", "airport", "airports", "aviation", "faa",
            "air travel"],
    "RRR": ["railroad", "railroads", "freight rail", "passenger rail", "amtrak",
            "rail safety"],
    "TRA": ["public transit", "mass transit", "transportation infrastructure",
            "surface transportation"],
    "ROD": ["highway", "highways", "road construction"],
    "SMB": ["small business", "small businesses", "small business administration",
            "main street businesses"],
    "GAM": ["casino", "gambling", "sports betting", "online gambling"],
    "SPO": ["youth sports", "professional sports", "college athletics",
            "name image likeness"],
    "TOB": ["tobacco", "vaping", "e-cigarettes", "cigarettes"],
    "ANI": ["animal welfare", "animal cruelty", "endangered species",
            "wildlife protection"],
    "NAT": ["public lands", "national parks", "natural resources", "mining"],
}


def _build_issue_matcher(mapping):
    """One alternation regex over all keywords + a lowercase keyword->code lookup.

    Single pass per document (like BILL_RE). Longest keywords first so, e.g.,
    'health care costs' wins over 'health care' at the same position. Boundaries
    use \\w lookarounds (not \\b) so punctuated phrases like 'k-12' / '401(k)'
    and phrase edges behave.
    """
    kw_to_code = {}
    for code, kws in mapping.items():
        for kw in kws:
            canon = " ".join(kw.lower().split())
            if canon in kw_to_code and kw_to_code[canon] != code:
                raise ValueError(f"keyword {canon!r} maps to both "
                                 f"{kw_to_code[canon]} and {code}")
            kw_to_code[canon] = code
    alts = sorted(kw_to_code, key=len, reverse=True)
    body = "|".join(r"\s+".join(re.escape(t) for t in kw.split()) for kw in alts)
    pattern = re.compile(r"(?<![\w])(?:" + body + r")(?![\w])", re.I)
    return pattern, kw_to_code


ISSUE_RE, KEYWORD_TO_CODE = _build_issue_matcher(ISSUE_KEYWORDS)


def extract_issues(text):
    """Yield (issue_code, keyword) once per distinct keyword found in text."""
    if not text:
        return
    seen = set()
    for m in ISSUE_RE.finditer(text):
        canon = " ".join(m.group(0).lower().split())
        code = KEYWORD_TO_CODE.get(canon)
        if code and (code, canon) not in seen:
            seen.add((code, canon))
            yield code, canon


def get_any(d, *keys, default=None):
    """First non-empty value among candidate keys (Senate JSON field names vary)."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def to_num(v):
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def strip_or_none(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


# ---------------------------------------------------------------- schema

DDL = """
CREATE TABLE IF NOT EXISTS press_releases (
  pr_id BIGINT, url TEXT, title TEXT, date TEXT, date_source TEXT, source TEXT,
  domain TEXT, scraper TEXT, bioguide_id TEXT, member_name TEXT, party TEXT,
  state TEXT, chamber TEXT, text TEXT, src_file TEXT, src_line INTEGER);

CREATE TABLE IF NOT EXISTS senate_filings (
  filing_uuid TEXT, filing_type TEXT, filing_period TEXT, filing_year INTEGER,
  income DOUBLE, expenses DOUBLE, registrant_id TEXT, registrant_name TEXT,
  house_registrant_id TEXT, client_id TEXT, client_name TEXT, client_state TEXT,
  client_description TEXT, posted TEXT, src_file TEXT, src_index INTEGER);

CREATE TABLE IF NOT EXISTS senate_activities (
  filing_uuid TEXT, activity_index INTEGER, general_issue_code TEXT,
  description TEXT, src_file TEXT, src_index INTEGER);

CREATE TABLE IF NOT EXISTS senate_lobbyists (
  filing_uuid TEXT, activity_index INTEGER, first_name TEXT, last_name TEXT,
  covered_position TEXT, is_new BOOLEAN, src_file TEXT, src_index INTEGER);

CREATE TABLE IF NOT EXISTS senate_gov_entities (
  filing_uuid TEXT, activity_index INTEGER, entity_name TEXT,
  src_file TEXT, src_index INTEGER);

CREATE TABLE IF NOT EXISTS senate_foreign_entities (
  filing_uuid TEXT, name TEXT, country TEXT, src_file TEXT, src_index INTEGER);

CREATE TABLE IF NOT EXISTS senate_contributions (
  filing_uuid TEXT, filer_type TEXT, filing_year INTEGER, registrant_name TEXT,
  lobbyist_name TEXT, pacs TEXT, src_file TEXT, src_index INTEGER);

CREATE TABLE IF NOT EXISTS senate_contribution_items (
  filing_uuid TEXT, item_index INTEGER, contribution_type TEXT, amount DOUBLE,
  payee TEXT, honoree TEXT, contributor_name TEXT, date TEXT,
  src_file TEXT, src_index INTEGER);

CREATE TABLE IF NOT EXISTS house_filings (
  filing_id TEXT, form TEXT, organization_name TEXT, client_name TEXT,
  senate_reg_id TEXT, house_reg_id TEXT, report_year INTEGER, report_period TEXT,
  income DOUBLE, expenses DOUBLE, specific_issues TEXT, src_path TEXT);

CREATE TABLE IF NOT EXISTS house_lobbyists (
  filing_id TEXT, ali_index INTEGER, first_name TEXT, last_name TEXT,
  covered_position TEXT, lobbyist_new TEXT, src_path TEXT);

-- One row per <alis><ali_info> block (real quarterly schema, verified 2026-07-04).
-- federal_agencies is the raw comma-separated string. Splitting it into clean
-- entities is entity-resolver work, not loader work.
CREATE TABLE IF NOT EXISTS house_alis (
  filing_id TEXT, ali_index INTEGER, issue_code TEXT, specific_issues TEXT,
  federal_agencies TEXT, src_path TEXT);

CREATE TABLE IF NOT EXISTS bill_mentions (
  dataset TEXT, record_key TEXT, bill TEXT, raw_match TEXT, src TEXT);

-- Press releases tagged with ALI issue codes via ISSUE_KEYWORDS. One row per
-- release/issue_code/keyword. pr_id + src_file:src_line is the raw-record
-- pointer (resolvable with show_record.py). See extract_issues / SHAKY_MAPPINGS.
CREATE TABLE IF NOT EXISTS press_issue_mentions (
  pr_id BIGINT, issue_code TEXT, keyword TEXT, src_file TEXT, src_line INTEGER);
"""

VIEWS = """
CREATE OR REPLACE VIEW members AS
  SELECT bioguide_id, any_value(member_name) AS name, any_value(party) AS party,
         any_value(state) AS state, any_value(chamber) AS chamber,
         count(*) AS n_releases
  FROM press_releases WHERE bioguide_id IS NOT NULL GROUP BY bioguide_id;

CREATE OR REPLACE VIEW v_spend_by_client_quarter AS
  SELECT client_name, filing_year, filing_period,
         sum(income) AS total_income, count(*) AS n_filings
  FROM senate_filings GROUP BY 1, 2, 3;

-- Income is filing-level. Attributing it to each activity's issue code
-- overstates multi-issue filings. Use for ranking/trend, not for exact dollars.
CREATE OR REPLACE VIEW v_spend_by_issue_quarter AS
  SELECT a.general_issue_code, f.filing_year, f.filing_period,
         sum(f.income) AS attributed_income, count(DISTINCT f.filing_uuid) AS n_filings
  FROM senate_activities a JOIN senate_filings f USING (filing_uuid)
  GROUP BY 1, 2, 3;

-- Press-side analogue of v_spend_by_issue_quarter, on the SAME (filing_year,
-- filing_period) grain so the two join directly. n_releases = distinct releases
-- mentioning the code that quarter (the volume metric). n_keyword_hits is the
-- looser total. Press month -> Senate quarter label. See queries/press_issue_coupling.sql.
CREATE OR REPLACE VIEW v_press_issue_quarter AS
  SELECT m.issue_code,
         CAST(substr(p.date, 1, 4) AS INTEGER) AS filing_year,
         CASE
           WHEN CAST(substr(p.date, 6, 2) AS INTEGER) BETWEEN 1 AND 3 THEN 'first_quarter'
           WHEN CAST(substr(p.date, 6, 2) AS INTEGER) BETWEEN 4 AND 6 THEN 'second_quarter'
           WHEN CAST(substr(p.date, 6, 2) AS INTEGER) BETWEEN 7 AND 9 THEN 'third_quarter'
           ELSE 'fourth_quarter'
         END AS filing_period,
         count(DISTINCT m.pr_id) AS n_releases,
         count(*) AS n_keyword_hits
  FROM press_issue_mentions m JOIN press_releases p ON p.pr_id = m.pr_id
  WHERE p.date IS NOT NULL AND length(p.date) >= 7
  GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW v_releases_by_member_month AS
  SELECT bioguide_id, any_value(member_name) AS name, substr(date, 1, 7) AS month,
         count(*) AS n_releases
  FROM press_releases GROUP BY bioguide_id, substr(date, 1, 7);

CREATE OR REPLACE VIEW v_covered_positions AS
  SELECT 'senate' AS dataset, filing_uuid AS record_key, first_name, last_name,
         covered_position FROM senate_lobbyists
  WHERE covered_position IS NOT NULL
  UNION ALL
  SELECT 'house', filing_id, first_name, last_name, covered_position
  FROM house_lobbyists WHERE covered_position IS NOT NULL;
"""


# ------------------------------------------------ lobbying free-text search layer
#
# The lobbying free-text (senate activity descriptions + House specific_issues) is
# where an industry actually describes what it lobbies on — and where an industry
# hidden under many issue codes and vague categories ("taxation") has to be found
# by VOCABULARY, not by issue-code filtering. This step builds the loader-owned,
# vocabulary-free search layer for that text, in two parts:
#
#   lobbying_freetext  — one row per activity/ali, unioning both chambers into a
#                        single doc surface with a stable doc_id AND a
#                        show_record.py-resolvable record_key (senate filing_uuid /
#                        House filing_id) + sub_index. This is the citation-keyed
#                        surface every downstream free-text tool reads.
#   FTS (BM25) index   — over lobbying_freetext.txt, so testing a candidate term is
#                        a query, not a code edit + rebuild (roadmap §1a). Discovery
#                        ONLY: the porter stemmer means BM25 'crypto' does NOT match
#                        'cryptocurrency', so the cited SERVING layer stays the
#                        deterministic whole-word keyword tagger (lobbying_issue_
#                        mentions, built by lead-scanner from a versioned vocabulary).
#
# doc_id is a build-local surrogate (FTS requires a single unique id column;
# senate_activities/house_alis are keyed by a composite). Citations never use
# doc_id — they use record_key — so its instability across rebuilds is harmless.
FREETEXT_TABLE = """
CREATE OR REPLACE TABLE lobbying_freetext AS
  SELECT row_number() OVER (ORDER BY dataset, record_key, sub_index) AS doc_id,
         dataset, record_key, sub_index, issue_code, txt, src_file, src_index
  FROM (
    SELECT 'senate' AS dataset, filing_uuid AS record_key,
           activity_index AS sub_index, general_issue_code AS issue_code,
           description AS txt, src_file, src_index
    FROM senate_activities
    WHERE description IS NOT NULL AND length(trim(description)) > 0
    UNION ALL
    SELECT 'house', filing_id, ali_index, issue_code,
           specific_issues, src_path, NULL
    FROM house_alis
    WHERE specific_issues IS NOT NULL AND length(trim(specific_issues)) > 0
  );
"""


def build_freetext_search(con):
    """Materialize lobbying_freetext + its FTS index. Idempotent (CREATE OR REPLACE
    + overwrite=1); safe to re-run in place on an already-loaded DB."""
    con.execute(FREETEXT_TABLE)
    n = con.execute("SELECT count(*) FROM lobbying_freetext").fetchone()[0]
    con.execute("INSTALL fts; LOAD fts;")
    # stemmer='none' so BM25 tokens match the raw words the keyword vocabulary uses
    # (we want 'stablecoin'/'defi' searchable verbatim, not porter-stemmed).
    con.execute("PRAGMA create_fts_index('lobbying_freetext', 'doc_id', 'txt', "
                "stemmer='none', overwrite=1)")
    return n


class Sink:
    """Batched inserts per table, staged through temp NDJSON files and COPY.

    duckdb's executemany runs row-by-row (~100x slower). NDJSON staging is
    immune to the CSV-dialect ambiguity that multi-line press text triggers:
    json.dumps escapes every field onto one line.
    """

    def __init__(self, con):
        self.con = con
        self.buf = {}
        self.counts = {}
        self.cols = {}

    def _columns(self, table):
        if table not in self.cols:
            self.cols[table] = [r[1] for r in self.con.execute(
                f"PRAGMA table_info('{table}')").fetchall()]
        return self.cols[table]

    def add(self, table, row):
        self.buf.setdefault(table, []).append(row)
        self.counts[table] = self.counts.get(table, 0) + 1
        if len(self.buf[table]) >= BATCH:
            self.flush(table)

    def flush(self, table=None):
        import os
        import tempfile
        for t in [table] if table else list(self.buf):
            rows = self.buf.get(t) or []
            if not rows:
                continue
            cols = self._columns(t)
            fd, tmp = tempfile.mkstemp(suffix=".ndjson")
            os.close(fd)
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    for row in rows:
                        f.write(json.dumps(dict(zip(cols, row)),
                                           ensure_ascii=False, default=str))
                        f.write("\n")
                self.con.execute(
                    f"COPY {t} FROM '{tmp.replace(chr(92), '/')}' (FORMAT json)")
            finally:
                os.unlink(tmp)
            self.buf[t] = []


# ---------------------------------------------------------------- press

def _parse_press_file(task):
    """Parse one press JSONL into per-release entries. Module-level (picklable
    args) so multiprocessing workers can run it; pr_id is NOT assigned here —
    it is a global running counter, so the parent assigns it while consuming
    results in file order, keeping ids identical to a sequential build.

    Returns [(line_no, base_row_without_pr_id, bills, issues), ...].
    """
    path, rel = task
    entries = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            mem = rec.get("member") or {}
            text = rec.get("text")
            base = (rec.get("url"), rec.get("title"), rec.get("date"),
                    rec.get("date_source"), rec.get("source"), rec.get("domain"),
                    rec.get("scraper"), get_any(mem, "bioguide_id"),
                    get_any(mem, "name"), get_any(mem, "party"),
                    get_any(mem, "state"), get_any(mem, "chamber"),
                    text, rel, line_no)
            entries.append((line_no, base,
                            list(extract_bills(text or "")),
                            list(extract_issues(text or ""))))
    return rel, entries


def load_press(sink, data_root, years, months=None, max_records=None, workers=None):
    root = data_root / "congress_press"
    files = sorted(root.glob("*.jsonl")) + sorted(root.glob("*/*.jsonl"))
    tasks = []
    for path in files:
        m = re.match(r"(\d{4})-(\d{2})", path.stem)
        if not m or int(m.group(1)) not in years:
            continue
        if months and (int(m.group(1)), int(m.group(2))) not in months:
            continue
        tasks.append((str(path), path.relative_to(data_root).as_posix()))

    if workers is None:
        import os
        workers = os.cpu_count() or 1
    pool = None
    if workers <= 1 or max_records:
        # max_records (smoke mode) stays sequential: deterministic + stops early.
        results = map(_parse_press_file, tasks)
    else:
        from multiprocessing import Pool
        pool = Pool(workers)
        # Ordered imap (one file per task) so the parent's pr_id counter walks
        # the same file order as a sequential run.
        results = pool.imap(_parse_press_file, tasks)

    n = 0
    for rel, entries in results:
        for line_no, base, bills, issues in entries:
            n += 1
            key = f"{rel}:{line_no}"
            sink.add("press_releases", (n, *base))
            for bill, raw in bills:
                sink.add("bill_mentions", ("press", key, bill, raw, rel))
            for code, kw in issues:
                sink.add("press_issue_mentions", (n, code, kw, rel, line_no))
            if max_records and n >= max_records:
                sink.flush()
                return n
    if pool:
        pool.close()
        pool.join()
    sink.flush()
    return n


# ---------------------------------------------------------------- senate

def load_senate(sink, data_root, years, max_records=None):
    done = {"filings": 0, "contributions": 0}
    for year in sorted(years):
        for kind in ("filings", "contributions"):
            if max_records and done[kind] >= max_records:
                continue
            path = data_root / "senate" / str(year) / kind / f"{kind}_{year}.json"
            if not path.exists():
                continue
            rel = path.relative_to(data_root).as_posix()
            with open(path, "rb") as f:
                for idx, rec in enumerate(ijson.items(f, "item")):
                    if kind == "filings":
                        _senate_filing(sink, rec, rel, idx)
                    else:
                        _senate_contribution(sink, rec, rel, idx)
                    done[kind] += 1
                    if max_records and done[kind] >= max_records:
                        break
    sink.flush()
    return done["filings"]


def _senate_filing(sink, rec, rel, idx):
    uuid = get_any(rec, "filing_uuid", "uuid")
    reg = rec.get("registrant") or {}
    cli = rec.get("client") or {}
    sink.add("senate_filings", (
        uuid, get_any(rec, "filing_type"), get_any(rec, "filing_period"),
        rec.get("filing_year"), to_num(get_any(rec, "income")),
        to_num(get_any(rec, "expenses")), strip_or_none(get_any(reg, "id")),
        strip_or_none(get_any(reg, "name")),
        strip_or_none(get_any(reg, "house_registrant_id")),
        strip_or_none(get_any(cli, "id", "client_id")),
        strip_or_none(get_any(cli, "name")), strip_or_none(get_any(cli, "state")),
        strip_or_none(get_any(cli, "general_description")),
        get_any(rec, "dt_posted", "posted"), rel, idx))
    for ai, act in enumerate(rec.get("lobbying_activities") or []):
        desc = strip_or_none(get_any(act, "description"))
        sink.add("senate_activities", (
            uuid, ai, get_any(act, "general_issue_code"), desc, rel, idx))
        for bill, raw in extract_bills(desc or ""):
            sink.add("bill_mentions", ("senate", uuid, bill, raw, rel))
        for lob in act.get("lobbyists") or []:
            person = lob.get("lobbyist") or lob
            sink.add("senate_lobbyists", (
                uuid, ai, strip_or_none(get_any(person, "first_name")),
                strip_or_none(get_any(person, "last_name")),
                strip_or_none(get_any(lob, "covered_position")),
                bool(get_any(lob, "new", "is_new", default=False)), rel, idx))
        for ge in act.get("government_entities") or []:
            name = ge.get("name") if isinstance(ge, dict) else ge
            sink.add("senate_gov_entities", (uuid, ai, strip_or_none(name), rel, idx))
    for fe in rec.get("foreign_entities") or []:
        if isinstance(fe, dict):
            sink.add("senate_foreign_entities", (
                uuid, strip_or_none(get_any(fe, "name")),
                strip_or_none(get_any(fe, "country")), rel, idx))


def _senate_contribution(sink, rec, rel, idx):
    uuid = get_any(rec, "filing_uuid", "uuid")
    reg = rec.get("registrant") or {}
    lob = rec.get("lobbyist") or {}
    lob_name = " ".join(x for x in (get_any(lob, "first_name"),
                                    get_any(lob, "last_name")) if x) or None
    pacs = rec.get("pacs") or []
    pacs_txt = "; ".join(p if isinstance(p, str) else str(get_any(p, "name", default=p))
                         for p in pacs) or None
    sink.add("senate_contributions", (
        uuid, get_any(rec, "filer_type"), rec.get("filing_year"),
        strip_or_none(get_any(reg, "name")), lob_name, pacs_txt, rel, idx))
    for ii, item in enumerate(rec.get("contribution_items") or []):
        sink.add("senate_contribution_items", (
            uuid, ii, get_any(item, "contribution_type", "type"),
            to_num(get_any(item, "amount")),
            strip_or_none(get_any(item, "payee_name", "payee")),
            strip_or_none(get_any(item, "honoree_name", "honoree")),
            strip_or_none(get_any(item, "contributor_name", "contributor")),
            get_any(item, "date", "contribution_date"), rel, idx))


# ---------------------------------------------------------------- house

DIR_RE = re.compile(r"^(\d{4})_(Registrations|1stQuarter|2ndQuarter|3rdQuarter|4thQuarter)_XML$")
PERIOD = {"Registrations": "RR", "1stQuarter": "Q1", "2ndQuarter": "Q2",
          "3rdQuarter": "Q3", "4thQuarter": "Q4"}


def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _ft(root, *names):
    """First non-blank text among candidate tag names, searched anywhere."""
    for name in names:
        for el in root.iter(name):
            if el.text and el.text.strip():
                return el.text.strip()
    return None


def _parse_house_file(task):
    """Parse one House XML into [(table, row), ...] rows. Module-level (and fed
    only picklable args) so multiprocessing workers can run it; all DuckDB
    writes stay in the parent process via Sink.

    Returns (rows, None) on success, (None, "file: error") on a parse failure.
    """
    xml_path, rel, year, period = task
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        return None, f"{Path(xml_path).name}: {e}"
    root = tree.getroot()
    _strip_ns(root)
    fid = Path(xml_path).stem
    form = "LD1" if root.tag.endswith("1") else "LD2"
    rows = []

    def add_lobbyists(parent, ali_index):
        for lob in parent.iter("lobbyist"):
            first = _ft(lob, "lobbyistFirstName", "firstName", "first_name")
            last = _ft(lob, "lobbyistLastName", "lastName", "last_name")
            if not (first or last):
                continue  # forms pad with empty <lobbyist> slots
            rows.append(("house_lobbyists", (
                fid, ali_index, first, last,
                _ft(lob, "coveredPosition", "covered_position"),
                _ft(lob, "lobbyistNew", "new"), rel)))

    all_desc = []
    ali_infos = root.findall(".//alis/ali_info")
    if ali_infos:
        # Quarterly (LD2) schema, verified against real 2026-Q1 files.
        for ai, ali in enumerate(ali_infos):
            descs = [d.text.strip() for d in ali.iter("description")
                     if d.text and d.text.strip()]
            desc = "\n".join(descs) or None
            if desc:
                all_desc.append(desc)
            rows.append(("house_alis", (
                fid, ai, _ft(ali, "issueAreaCode", "ali_Code"), desc,
                _ft(ali, "federal_agencies", "federalAgencies"), rel)))
            add_lobbyists(ali, ai)
    else:
        # Registration (LD1) / older layout per the data manual: flat
        # ali_Code list, lobbyists at document level. Verify when a
        # Registrations_XML directory lands.
        for ai, ali in enumerate(root.iter("ali_Code")):
            if ali.text and ali.text.strip():
                rows.append(("house_alis", (fid, ai, ali.text.strip(),
                                            None, None, rel)))
        descs = [d.text.strip() for d in root.findall(".//specific_issues//description")
                 if d.text and d.text.strip()]
        descs += [el.text.strip() for el in root.findall(".//specific_issues")
                  if el.text and el.text.strip()]
        all_desc.extend(descs)
        add_lobbyists(root, None)

    spec = "\n".join(all_desc) or None
    rows.append(("house_filings", (
        fid, form, _ft(root, "organizationName", "organizationname"),
        _ft(root, "clientName", "clientname"),
        _ft(root, "senateID", "senateId", "senateid"),
        _ft(root, "houseID", "houseId", "houseid"),
        year, period, to_num(_ft(root, "income")),
        to_num(_ft(root, "expenses")), spec, rel)))
    for bill, raw in extract_bills(spec or ""):
        rows.append(("bill_mentions", ("house", fid, bill, raw, rel)))
    return rows, None


def load_house(sink, data_root, years, periods=None, max_records=None, workers=None):
    house = data_root / "house"
    n, errors = 0, []
    if not house.exists():
        return n, errors
    tasks = []
    for d in sorted(house.iterdir()):
        m = DIR_RE.match(d.name) if d.is_dir() else None
        if not m or int(m.group(1)) not in years:
            continue
        year, period = int(m.group(1)), PERIOD[m.group(2)]
        if periods and period not in periods:
            continue
        tasks.extend((str(p), p.relative_to(data_root).as_posix(), year, period)
                     for p in sorted(d.glob("*.xml")))

    if workers is None:
        import os
        workers = os.cpu_count() or 1
    # max_records (smoke mode) keeps the deterministic sequential order so a
    # capped run always loads the same files.
    if workers <= 1 or max_records:
        results = map(_parse_house_file, tasks)
    else:
        from multiprocessing import Pool
        pool = Pool(workers)
        results = pool.imap_unordered(_parse_house_file, tasks, chunksize=64)

    for rows, err in results:
        if err:
            errors.append(err)
            continue
        for table, row in rows:
            sink.add(table, row)
        n += 1
        if max_records and n >= max_records:
            break
    if workers > 1 and not max_records:
        pool.close()
        pool.join()
    sink.flush()
    return n, errors


# ---------------------------------------------------------------- sanity

def sanity_report(con, db_path, years, house_errors):
    lines = ["# Sanity report", ""]
    # Scope to the main schema: the FTS index adds internal tables (dict/docs/
    # terms/...) in its own fts_main_* schema that must not be counted here.
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' AND table_schema='main' ORDER BY 1").fetchall()]
    lines.append("| table | rows |")
    lines.append("|---|---|")
    counts = {}
    for t in tables:
        c = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        counts[t] = c
        lines.append(f"| {t} | {c:,} |")
    lines.append("")
    if 2025 in years:
        lines.append("## 2025 vs data manual")
        lines.append("")
        lines.append("| dataset | loaded (2025) | manual says | delta |")
        lines.append("|---|---|---|---|")
        loaded = {
            "press_releases": con.execute(
                "SELECT count(*) FROM press_releases WHERE src_file LIKE '%2025-%'"
            ).fetchone()[0],
            "senate_filings": con.execute(
                "SELECT count(*) FROM senate_filings WHERE filing_year=2025"
            ).fetchone()[0],
            "senate_contributions": con.execute(
                "SELECT count(*) FROM senate_contributions WHERE filing_year=2025"
            ).fetchone()[0],
            "house_filings": con.execute(
                "SELECT count(*) FROM house_filings WHERE report_year=2025"
            ).fetchone()[0],
        }
        for k, ref in MANUAL_2025.items():
            got = loaded[k]
            delta = (got - ref) / ref * 100 if ref else 0
            flag = "" if abs(delta) < 10 else "  ⚠️"
            lines.append(f"| {k} | {got:,} | ~{ref:,} | {delta:+.1f}%{flag} |")
        lines.append("")
        lines.append("Deltas beyond ±10% mean either a partial download or a parser "
                     "mismatch — investigate before trusting downstream queries.")
    if house_errors:
        lines.append("")
        lines.append(f"## House XML parse errors: {len(house_errors)}")
        lines.extend(f"- {e}" for e in house_errors[:20])
    report = "\n".join(lines) + "\n"
    out = db_path.parent / "sanity_report.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"Sanity report written to {out}")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", required=True, type=Path)
    ap.add_argument("--db", type=Path, default=Path("db/lda.duckdb"))
    ap.add_argument("--years", nargs="*", type=int,
                    help="Years to load (default: everything present)")
    ap.add_argument("--sample", metavar="YYYY-QN",
                    help="Smoke mode: one quarter of press+house, capped Senate records")
    ap.add_argument("--max-records", type=int,
                    help="Cap per-dataset primary records (smoke/testing)")
    ap.add_argument("--workers", type=int,
                    help="Parallel workers for press JSONL + House XML parsing "
                         "(default: cpu count; 1 = sequential)")
    args = ap.parse_args()

    data_root = args.data_root
    if not data_root.exists():
        sys.exit(f"data root not found: {data_root}")

    years = set(args.years or range(2022, 2027))
    months = periods = None
    max_records = args.max_records
    if args.sample:
        m = re.match(r"^(\d{4})-Q([1-4])$", args.sample)
        if not m:
            sys.exit("--sample must look like 2025-Q1")
        y, q = int(m.group(1)), int(m.group(2))
        years = {y}
        months = {(y, mm) for mm in range(3 * q - 2, 3 * q + 1)}
        periods = {"RR", f"Q{q}"}
        max_records = max_records or 5000

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.db))
    for stmt in DDL.split(";"):
        if stmt.strip():
            con.execute(stmt)

    import time as _time
    sink = Sink(con)
    t0 = _time.time()
    print(f"Loading press releases ({sorted(years)}) ...")
    n_press = load_press(sink, data_root, years, months, max_records,
                         workers=args.workers)
    t1 = _time.time()
    print(f"  {n_press:,} releases in {t1 - t0:.1f}s")
    print("Loading Senate LDA ...")
    n_sen = load_senate(sink, data_root, years, max_records)
    t2 = _time.time()
    print(f"  {n_sen:,} filings in {t2 - t1:.1f}s")
    print("Loading House LDA ...")
    n_house, house_errors = load_house(sink, data_root, years, periods, max_records,
                                       workers=args.workers)
    t3 = _time.time()
    print(f"  {n_house:,} filings ({len(house_errors)} parse errors) in {t3 - t2:.1f}s")

    for stmt in VIEWS.split(";"):
        if stmt.strip():
            con.execute(stmt)

    print("Building lobbying free-text search layer (lobbying_freetext + FTS) ...")
    n_ft = build_freetext_search(con)
    print(f"  {n_ft:,} free-text docs indexed")

    sanity_report(con, args.db, years, house_errors)
    con.close()
    print(f"Done: {args.db}")


if __name__ == "__main__":
    main()
