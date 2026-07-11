"""Per-player raw-filing index for the crypto package (2026-07-09, Rob's ask:
"a way to link to all the filings that are included so people can see the raw
filings").

Writes data/crypto_player_filings.csv: every crypto-tagged senate filing behind
every player on the map, with a public lda.senate.gov URL per filing (URL
pattern verified 2026-07-09 against a988040b-8776-43bc-9311-58b95dcfda73 —
Coinbase/Checkmate 2026-Q1). The player->filing join is EXACTLY the one
export_crypto.py's crypto_players.csv uses, so per-player counts here reconcile
with the map's filing counts. Registrations included (they're part of the tagged
set the map counts); amounts are per-filing reported figures (ranking signals,
not summable — see package README).

Run from the gain-investigation repo root.
"""
import csv
import os
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
OUT = os.path.join(REPO, "out", "packages", "crypto", "data")

Q = """
WITH crypto_clients AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='CRYPTO' AND lim.dataset='senate'),
kw AS (
  SELECT record_key, string_agg(DISTINCT keyword, '; ') AS matched_keywords
  FROM lobbying_issue_mentions WHERE tag='CRYPTO' AND dataset='senate' GROUP BY 1),
resolved AS (
  -- DISTINCT: the alias join fans out when one raw client_name carries several
  -- alias rows (different senate ids under one entity)
  SELECT DISTINCT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         k.matched_keywords
  FROM crypto_clients c
  JOIN senate_filings sf ON sf.filing_uuid=c.filing_uuid
  JOIN kw k ON k.record_key=c.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL)
SELECT player, entity_id, filing_year, filing_period, filing_type,
       registrant_name, amount, matched_keywords, filing_uuid
FROM resolved
ORDER BY player, filing_year, filing_period, filing_uuid
"""

PQ = {"first_quarter": "Q1", "second_quarter": "Q2", "third_quarter": "Q3",
      "fourth_quarter": "Q4", "mid_year": "MY", "year_end": "YE"}

# Second index: the filings behind EACH QUARTER of the trend chart, using EXACTLY
# the chart's semantics (export_crypto.py q_trend `ded` CTE: amendments deduped on
# (registrant_id, client_id, filing_year, filing_period) latest-by-posted,
# registrations excluded) — so the per-quarter list count EQUALS the plotted count
# and the widget can be validated row by row.
TREND_Q = """
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='CRYPTO' AND lim.dataset='senate'),
ded AS (
  SELECT sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name,
         coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM senate_filings sf
  JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1),
kw AS (
  SELECT record_key, string_agg(DISTINCT keyword, '; ') AS matched_keywords
  FROM lobbying_issue_mentions WHERE tag='CRYPTO' AND dataset='senate' GROUP BY 1)
SELECT DISTINCT d.filing_year, d.filing_period, d.player, d.registrant_name, d.amount,
       d.filing_type, k.matched_keywords, d.filing_uuid
FROM ded d JOIN kw k ON k.record_key = d.filing_uuid
ORDER BY d.filing_year, d.filing_period, d.amount DESC NULLS LAST, d.filing_uuid
"""

con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)
rows = con.execute(Q).fetchall()
con.close()

path = os.path.join(OUT, "crypto_player_filings.csv")
with open(path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["player", "entity_id", "filing_year", "filing_period", "filing_type",
                "registrant_name", "reported_amount", "matched_keywords", "filing_uuid",
                "lda_public_url"])
    for player, eid, yr, per, ftype, reg, amt, kws, uuid in rows:
        w.writerow([player, eid, yr, per, ftype, reg, amt, kws, uuid,
                    f"https://lda.senate.gov/filings/public/filing/{uuid}/print/"])

players = {r[0] for r in rows}
print(f"[csv] crypto_player_filings.csv: {len(rows)} filings across {len(players)} players")

# reconcile per-player counts against the shipped crypto_players.csv
counts = {}
for r in rows:
    counts[r[0]] = counts.get(r[0], 0) + (1 if True else 0)
uuids_per = {}
for r in rows:
    uuids_per.setdefault(r[0], set()).add(r[8])
mism = 0
with open(os.path.join(OUT, "crypto_players.csv"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        want = int(row["crypto_filings_senate"])
        got = len(uuids_per.get(row["player"], ()))
        if want != got:
            mism += 1
            print(f"  MISMATCH {row['player'][:40]}: players.csv={want} filings.csv={got}")
print("reconciliation vs crypto_players.csv:", "OK — every player's filing count matches"
      if mism == 0 else f"{mism} MISMATCHES")

# ---- trend-filings index (chart-semantics dedup) + reconciliation vs the chart CSV
con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)
trows = con.execute(TREND_Q).fetchall()
con.close()
tpath = os.path.join(OUT, "crypto_trend_filings.csv")
with open(tpath, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["filing_year", "filing_period", "player", "registrant_name",
                "reported_amount", "filing_type", "matched_keywords", "filing_uuid",
                "lda_public_url"])
    for yr, per, player, reg, amt, ftype, kws, uuid in trows:
        w.writerow([yr, per, player, reg, amt, ftype, kws, uuid,
                    f"https://lda.senate.gov/filings/public/filing/{uuid}/print/"])
print(f"[csv] crypto_trend_filings.csv: {len(trows)} deduped filings")

per_q = {}
for yr, per, *_ in trows:
    per_q[(str(yr), per)] = per_q.get((str(yr), per), 0) + 1
mism = 0
with open(os.path.join(OUT, "crypto_quarterly_trend.csv"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        want = int(row["crypto_filings"])
        got = per_q.get((row["filing_year"], row["filing_period"]), 0)
        if want != got:
            mism += 1
            print(f"  MISMATCH {row['filing_year']} {row['filing_period']}: "
                  f"trend.csv={want} trend_filings.csv={got}")
print("reconciliation vs crypto_quarterly_trend.csv:",
      "OK — every quarter's filing count matches the chart"
      if mism == 0 else f"{mism} MISMATCHES")
