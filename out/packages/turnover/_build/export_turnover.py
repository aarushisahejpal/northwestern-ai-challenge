"""Turnover-package data export (P3 quarterly turnover / termination tracker).

Everything the dashboard shows is produced HERE, by calling the P3 tool's own
query functions (skills/lead-scanner/scripts/lda_turnover.py) — the dashboard
cannot drift from the tool. A recording connection captures the EXACT SQL each
section executed and writes it to data/turnover_<QTAG>_queryinfo_sql.json, which
viz_build.py embeds in the per-widget "View query info" modals.

One run = one report quarter. Quarter-scoped files carry the quarter tag
(<QTAG> = 2025Q4, 2026Q1, ...); viz_build.py turns every exported quarter into a
switchable view in the one dashboard. Writes to out/packages/turnover/data/:
  turnover_<QTAG>_summary.csv      KPI numbers (target vs prev qtr vs same qtr prior year)
  turnover_<QTAG>_terminations.csv every termination in the target quarter + lda URL
  turnover_<QTAG>_new_engagements.csv  every new engagement + lda URL
  turnover_<QTAG>_new_engagement_filings.csv  every target-quarter filing per new pair
  turnover_<QTAG>_swaps.csv        every swap/in-house move + BOTH filing URLs
  turnover_<QTAG>_firm_churn.csv   per-registrant lost/signed scoreboard
  turnover_<QTAG>_term_history.csv per-quarter income rows behind each displayed termination
                                   bar (they sum to the bar; reconciled at export)
  turnover_<QTAG>_churn_clients.csv  displayed firms' lost + signed client lists + URLs
  turnover_<QTAG>_queryinfo_sql.json the SQL actually executed, per widget
  turnover_quarterly_trend.csv     P3a per-quarter counts (corpus-wide; identical every run)
  turnover_trend_top.csv           per-quarter top terminations + hires (corpus-wide)

Run from the repo root:  .venv/Scripts/python out/packages/turnover/_build/export_turnover.py [2026Q1]
"""
import csv
import importlib.util
import json
import os
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
OUT = os.path.join(REPO, "out", "packages", "turnover", "data")
os.makedirs(OUT, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "lda_turnover", os.path.join(REPO, "skills", "lead-scanner", "scripts", "lda_turnover.py"))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

TARGET = sys.argv[1] if len(sys.argv) > 1 else "2025Q4"
t = T.parse_quarter(TARGET)
QTAG = T.qlabel(t).replace("-", "")   # e.g. 2025Q4 — quarter-scoped files carry it;
                                      # corpus-wide files (trend, trend_top) stay unsuffixed
LDA_F = "https://lda.senate.gov/filings/public/filing/{}/print/"


class RecordingCon:
    """duckdb connection proxy: logs every SQL statement executed through it."""
    def __init__(self, con):
        self._con = con
        self.log = []

    def execute(self, sql, *a, **k):
        self.log.append(sql)
        return self._con.execute(sql, *a, **k)

    def take(self):
        out, self.log = self.log, []
        return out


raw_con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)
con = RecordingCon(raw_con)
qi_sql = {}


def wcsv(name, cols, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"[csv] {name}: {len(rows)} rows")


# ---------- summary KPIs (the tool's own counts) ----------
con.take()
n_term, n_new = T.counts_for(con, t)
prev = T.counts_for(con, t - 1)
yoy = T.counts_for(con, t - 4)
qi_sql["kpis"] = con.take()[0]

# ---------- P3b terminations ----------
term_rows = T.terminations(con, t)
qi_sql["terms"] = con.take()[0]
wcsv(f"turnover_{QTAG}_terminations.csv",
     ["registrant", "client", "trail4_income", "n_quarters", "first_seen",
      "new_this_q", "re_engaged", "term_uuid", "lda_public_url"],
     [[r[0], r[1], r[2], r[3], T.qlabel(r[4]), r[5], r[6], r[7], LDA_F.format(r[7])]
      for r in term_rows])

# ---------- P3c new engagements ----------
new_rows = T.new_engagements(con, t)
qi_sql["hires"] = con.take()[0]
wcsv(f"turnover_{QTAG}_new_engagements.csv",
     ["registrant", "client", "q_income", "cite_uuid", "registration_only",
      "terminated_same_q", "lda_public_url"],
     [list(r) + [LDA_F.format(r[3])] for r in new_rows])

# ---------- P3d swaps ----------
swap_rows = T.swaps(con, t, 1)
qi_sql["swaps"] = con.take()[0]
wcsv(f"turnover_{QTAG}_swaps.csv",
     ["client", "old_firm", "new_firm", "hire_dq", "move", "client_q_canonical_spend",
      "term_uuid", "term_lda_url", "hire_uuid", "hire_lda_url"],
     [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], LDA_F.format(r[6]), r[7], LDA_F.format(r[7])]
      for r in swap_rows])

# ---------- P3e firm churn ----------
firm_rows = T.firm_churn(con, t)
qi_sql["churn"] = con.take()[0]
wcsv(f"turnover_{QTAG}_firm_churn.csv",
     ["registrant", "n_lost", "lost_trail4_income", "n_new", "net"], firm_rows)

n_inhouse = sum(1 for r in swap_rows if r[4])
n_swap_clients = len({r[0] for r in swap_rows})
wcsv(f"turnover_{QTAG}_summary.csv",
     ["quarter", "terminations", "new_engagements", "swap_rows", "swap_clients",
      "inhouse_moves", "prev_q_terminations", "prev_q_new",
      "yoy_q_terminations", "yoy_q_new",
      "top_termination_client", "top_termination_registrant", "top_termination_trail4"],
     [[T.qlabel(t), n_term, n_new, len(swap_rows), n_swap_clients, n_inhouse,
       prev[0], prev[1], yoy[0], yoy[1],
       term_rows[0][1], term_rows[0][0], term_rows[0][2]]])

# ---------- P3a quarterly trend ----------
Q_TREND = f"""
WITH {T.PAIRS.strip()},
term AS (
  SELECT qidx, count(DISTINCT (registrant_id, ckey)) n_term
  FROM pairs WHERE regexp_matches(filing_type, '{T.TERM_RE}') GROUP BY 1),
new_p AS (
  SELECT first_q AS qidx, count(*) n_new
  FROM (SELECT registrant_id, ckey, min(qidx) first_q FROM pairs GROUP BY 1,2)
  GROUP BY 1)
SELECT qidx, coalesce(t.n_term, 0), coalesce(n.n_new, 0)
FROM term t FULL JOIN new_p n USING (qidx)
ORDER BY qidx"""
trend = con.execute(Q_TREND).fetchall()
qi_sql["trend"] = con.take()[0]
wcsv("turnover_quarterly_trend.csv",
     ["quarter", "terminations", "new_engagements"],
     [[T.qlabel(q), a, b] for q, a, b in trend])
# reconcile trend row vs the tool's counts for the target quarter
tr = {q: (a, b) for q, a, b in trend}
assert tr[t] == (n_term, n_new), f"trend row {tr[t]} != tool counts {(n_term, n_new)}"
print(f"reconciliation trend[{T.qlabel(t)}] == counts_for: OK {tr[t]}")

# ---------- trend click-through: per-quarter top terminations + top hires ----------
TOP_PER_Q = 30
Q_TREND_TOP = f"""
WITH {T.PAIRS.strip()},
dedup AS (
  SELECT * FROM pairs WHERE filing_type NOT IN ('RR','RA')
  QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey, filing_year,
    filing_period ORDER BY posted DESC, filing_uuid) = 1),
term AS (   -- every termination, with trail-4 income relative to ITS quarter
  SELECT p.qidx, p.registrant_id, p.ckey, min(p.registrant_name) registrant,
         min(p.c_canon) client, min(p.filing_uuid) term_uuid
  FROM pairs p WHERE regexp_matches(p.filing_type, '{T.TERM_RE}')
  GROUP BY 1,2,3),
term_v AS (
  SELECT te.*, (SELECT sum(d.income) FROM dedup d
                WHERE d.registrant_id = te.registrant_id AND d.ckey = te.ckey
                  AND d.qidx > te.qidx-4 AND d.qidx <= te.qidx) trail4,
         'term' AS kind
  FROM term te),
hire_v AS (   -- every new engagement, with its first-quarter deduped income
  SELECT f.first_q AS qidx, f.registrant_id, f.ckey, f.registrant, f.client,
         coalesce(d.filing_uuid, f.first_uuid) AS term_uuid,
         d.income AS trail4, 'hire' AS kind
  FROM (SELECT registrant_id, ckey, min(registrant_name) registrant,
               min(c_canon) client, min(qidx) first_q,
               arg_min(filing_uuid, (qidx, filing_uuid)) first_uuid
        FROM pairs GROUP BY 1,2) f
  LEFT JOIN dedup d ON d.registrant_id = f.registrant_id AND d.ckey = f.ckey
       AND d.qidx = f.first_q),
u AS (SELECT * FROM term_v UNION ALL SELECT * FROM hire_v)
SELECT qidx, kind, registrant, client, trail4::BIGINT, term_uuid
FROM (SELECT *, row_number() OVER (PARTITION BY qidx, kind
        ORDER BY coalesce(trail4,0) DESC, client, registrant) rn FROM u)
WHERE rn <= {TOP_PER_Q}
ORDER BY qidx, kind, rn"""
tt_rows = con.execute(Q_TREND_TOP).fetchall()
qi_sql["trend_top"] = con.take()[0]
wcsv("turnover_trend_top.csv",
     ["quarter", "kind", "registrant", "client", "income_trail4_or_firstq", "filing_uuid",
      "lda_public_url"],
     [[T.qlabel(q), k, rg, cl, v, u, LDA_F.format(u)] for q, k, rg, cl, v, u in tt_rows])
# reconcile the target quarter's top-terminations list against the tool's ranking
tool_top = [(r[1], r[0], r[2]) for r in term_rows[:TOP_PER_Q]]
mine_top = [(cl, rg, v) for q, k, rg, cl, v, u in tt_rows if q == t and k == "term"]
assert tool_top == mine_top, "trend-top target-quarter terminations diverge from the tool ranking"
print(f"reconciliation trend_top[{T.qlabel(t)}] == tool terminations top-{TOP_PER_Q}: OK")

# ---------- displayed-bar audits: engagement history behind the top terminations ----------
N_DISPLAY = 16
Q_HIST = f"""
WITH {T.PAIRS.strip()},
dedup AS (
  SELECT * FROM pairs WHERE filing_type NOT IN ('RR','RA')
  QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey, filing_year,
    filing_period ORDER BY posted DESC, filing_uuid) = 1),
term AS (
  SELECT registrant_id, ckey, min(registrant_name) registrant,
         min(c_canon) client, min(filing_uuid) term_uuid
  FROM pairs WHERE regexp_matches(filing_type, '{T.TERM_RE}') AND qidx = {t}
  GROUP BY 1,2),
ranked AS (
  SELECT * FROM (
    SELECT te.*, (SELECT sum(d.income) FROM dedup d
                  WHERE d.registrant_id = te.registrant_id AND d.ckey = te.ckey
                    AND d.qidx > {t}-4 AND d.qidx <= {t}) trail4
    FROM term te)
  ORDER BY coalesce(trail4,0) DESC, client, registrant LIMIT {N_DISPLAY})
SELECT r.client, r.registrant, r.term_uuid, r.trail4::BIGINT,
       d.qidx, d.income::BIGINT, d.filing_uuid, d.filing_type,
       (d.qidx > {t}-4 AND d.qidx <= {t}) AS in_trail4
FROM ranked r JOIN dedup d USING (registrant_id, ckey)
ORDER BY r.trail4 DESC, r.client, d.qidx"""
hist = con.execute(Q_HIST).fetchall()
qi_sql["hist"] = con.take()[0]
wcsv(f"turnover_{QTAG}_term_history.csv",
     ["client", "registrant", "term_uuid", "bar_trail4_income", "quarter", "income",
      "filing_uuid", "filing_type", "in_trail4_window", "lda_public_url"],
     [[c, rg, tu, b, T.qlabel(q), inc, u, ft, itw, LDA_F.format(u)]
      for c, rg, tu, b, q, inc, u, ft, itw in hist])
# reconcile: per displayed pair, sum(income of in-window rows) == the bar
sums = {}
for c, rg, tu, b, q, inc, u, ft, itw in hist:
    if itw:
        sums[(c, rg)] = sums.get((c, rg), 0) + (inc or 0)
mism = 0
for r in term_rows[:N_DISPLAY]:
    want = r[2] or 0
    got = sums.get((r[1], r[0]), 0)
    if abs(want - got) > 1:
        mism += 1
        print(f"  MISMATCH history {r[1][:40]!r}: bar={want:,} rows={got:,}")
print("reconciliation term_history vs bars:",
      "OK — every displayed bar's in-window rows sum to it" if mism == 0 else f"{mism} MISMATCHES")

# ---------- churn click-through: displayed firms' lost + signed clients ----------
N_FIRMS = 14
disp_firms = [r[0] for r in firm_rows[:N_FIRMS]]
con._con.execute("CREATE OR REPLACE TEMP TABLE _firms(registrant TEXT)")
con._con.executemany("INSERT INTO _firms VALUES (?)", [(f,) for f in disp_firms])
Q_CHURN_CLIENTS = f"""
WITH {T.PAIRS.strip()},
dedup AS (
  SELECT * FROM pairs WHERE filing_type NOT IN ('RR','RA')
  QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey, filing_year,
    filing_period ORDER BY posted DESC, filing_uuid) = 1),
firm_names AS (   -- EXACTLY the scoreboard's name derivation (lda_turnover.firm_churn):
                  -- min name over the target quarter's T-family rows when the firm has
                  -- terminations, else min over all rows (a renamed firm — Ballard →
                  -- 'BALLARD PARTNERS, LLC' — otherwise fails the name join)
  SELECT registrant_id,
         coalesce(min(registrant_name) FILTER (WHERE regexp_matches(filing_type,
                    '{T.TERM_RE}') AND qidx = {t}),
                  min(registrant_name)) AS registrant
  FROM pairs GROUP BY 1),
firm_ids AS (
  SELECT fn.registrant_id, fn.registrant
  FROM firm_names fn JOIN _firms f USING (registrant)),
lost AS (
  SELECT fi.registrant, 'lost' AS kind, min(p.c_canon) client,
         (SELECT sum(d.income) FROM dedup d
          WHERE d.registrant_id = p.registrant_id AND d.ckey = p.ckey
            AND d.qidx > {t}-4 AND d.qidx <= {t})::BIGINT AS amount,
         min(p.filing_uuid) AS filing_uuid
  FROM pairs p JOIN firm_ids fi USING (registrant_id)
  WHERE regexp_matches(p.filing_type, '{T.TERM_RE}') AND p.qidx = {t}
  GROUP BY fi.registrant, p.registrant_id, p.ckey),
signed AS (
  SELECT fi.registrant, 'signed' AS kind, f.client,
         d.income::BIGINT AS amount, coalesce(d.filing_uuid, f.first_uuid) AS filing_uuid
  FROM (SELECT registrant_id, ckey, min(c_canon) client, min(qidx) first_q,
               arg_min(filing_uuid, (qidx, filing_uuid)) first_uuid
        FROM pairs GROUP BY 1,2 HAVING min(qidx) = {t}) f
  JOIN firm_ids fi USING (registrant_id)
  LEFT JOIN dedup d ON d.registrant_id = f.registrant_id AND d.ckey = f.ckey AND d.qidx = {t})
SELECT registrant, kind, client, amount, filing_uuid
FROM (SELECT * FROM lost UNION ALL SELECT * FROM signed)
ORDER BY registrant, kind, coalesce(amount,0) DESC, client"""
cc_rows = con.execute(Q_CHURN_CLIENTS).fetchall()
qi_sql["churn_clients"] = con.take()[0]
wcsv(f"turnover_{QTAG}_churn_clients.csv",
     ["registrant", "kind", "client", "amount", "filing_uuid", "lda_public_url"],
     [[rg, k, cl, a, u, LDA_F.format(u)] for rg, k, cl, a, u in cc_rows])
# reconcile counts per displayed firm vs the scoreboard
by_firm = {}
for rg, k, cl, a, u in cc_rows:
    d = by_firm.setdefault(rg, {"lost": 0, "signed": 0})
    d[k] += 1
mism = 0
for r in firm_rows[:N_FIRMS]:
    got = by_firm.get(r[0], {"lost": 0, "signed": 0})
    if got["lost"] != r[1] or got["signed"] != r[3]:
        mism += 1
        print(f"  MISMATCH churn {r[0][:40]!r}: scoreboard lost={r[1]}/new={r[3]} "
              f"lists lost={got['lost']}/signed={got['signed']}")
print("reconciliation churn_clients vs scoreboard:",
      "OK — every displayed firm's lists match its lost/signed counts" if mism == 0 else f"{mism} MISMATCHES")

# ---------- new-engagement click-through: all target-quarter filings of top hires ----------
Q_HIRE_FILINGS = f"""
WITH {T.PAIRS.strip()},
firstq AS (
  SELECT registrant_id, ckey, min(registrant_name) registrant, min(c_canon) client
  FROM pairs GROUP BY 1,2 HAVING min(qidx) = {t})
SELECT f.client, f.registrant, p.filing_uuid, p.filing_type, p.income::BIGINT
FROM firstq f JOIN pairs p USING (registrant_id, ckey)
WHERE p.qidx = {t}
ORDER BY f.client, f.registrant, p.filing_type, p.filing_uuid"""
hf_rows = con.execute(Q_HIRE_FILINGS).fetchall()
qi_sql["hire_filings"] = con.take()[0]
wcsv(f"turnover_{QTAG}_new_engagement_filings.csv",
     ["client", "registrant", "filing_uuid", "filing_type", "reported_income", "lda_public_url"],
     [[c, rg, u, ft, inc, LDA_F.format(u)] for c, rg, u, ft, inc in hf_rows])

with open(os.path.join(OUT, f"turnover_{QTAG}_queryinfo_sql.json"), "w", encoding="utf-8") as f:
    json.dump({"target_quarter": T.qlabel(t), "sql": qi_sql}, f, ensure_ascii=False, indent=1)
print(f"[json] turnover_{QTAG}_queryinfo_sql.json:", ", ".join(qi_sql.keys()))

raw_con.close()
print("\nDONE —", T.qlabel(t))
