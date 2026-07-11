"""AIPAC package exporter (2026-07-08).
Writes CSVs to out/packages/aipac/data/. Run from repo root.
Senate-primary; AIPAC self-files (registrant == client), no amendments in window.
The Israel-policy co-lobby scan is an EXPLORATORY free-text scan (ad-hoc regex),
not the curated lexicon serving table — labeled as such in the package README.
"""
import duckdb, json, csv, os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
OUT = os.path.join(REPO, "out", "packages", "aipac", "data")
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)

AIPAC = "upper(registrant_name) LIKE '%AMERICAN ISRAEL PUBLIC AFFAIRS%'"
ISRAEL_RE = r"\b(israel|israeli|israelis|antisemitism|anti-semitism|abraham accords|gaza|hamas|hezbollah|iron dome|west bank|palestinian|palestine|golan heights|jerusalem)\b"
QORD = "CASE filing_period WHEN 'first_quarter' THEN 1 WHEN 'second_quarter' THEN 2 WHEN 'third_quarter' THEN 3 ELSE 4 END"

def wcsv(name, q_or_rows, cols=None):
    if isinstance(q_or_rows, str):
        cur = con.execute(q_or_rows)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    else:
        rows = q_or_rows
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    print(f"[csv] {name}: {len(rows)} rows")
    return cols, rows

# 1. quarterlies
wcsv("aipac_quarterlies.csv", f"""
SELECT filing_year, filing_period, filing_type,
       coalesce(income, expenses)::BIGINT AS reported_amount,
       substr(posted,1,10) AS posted, filing_uuid AS show_record_key
FROM senate_filings WHERE {AIPAC}
ORDER BY filing_year, {QORD}""")

# 2. activities (their own words)
wcsv("aipac_activities.csv", f"""
SELECT f.filing_year, f.filing_period, a.general_issue_code, a.description,
       f.filing_uuid AS show_record_key
FROM senate_activities a JOIN senate_filings f USING (filing_uuid)
WHERE {AIPAC}
ORDER BY f.filing_year, {QORD.replace('filing_period','f.filing_period')}, a.general_issue_code""")

# 3. who is lobbied
wcsv("aipac_gov_entities.csv", f"""
SELECT g.entity_name, count(*) AS mentions,
       min(f.filing_year) AS first_year, max(f.filing_year) AS last_year
FROM senate_gov_entities g JOIN senate_filings f USING (filing_uuid)
WHERE {AIPAC}
GROUP BY 1 ORDER BY mentions DESC""")

# 4. lobbyists + covered positions
wcsv("aipac_lobbyists.csv", f"""
SELECT l.first_name, l.last_name,
       max(nullif(trim(l.covered_position),'')) AS covered_position,
       min(f.filing_year) AS first_year, max(f.filing_year) AS last_year,
       count(DISTINCT f.filing_uuid) AS filings
FROM senate_lobbyists l JOIN senate_filings f USING (filing_uuid)
WHERE {AIPAC}
GROUP BY 1,2 ORDER BY filings DESC, last_year DESC""")

# 5. bills AIPAC lobbies
_, aipac_bills = wcsv("aipac_bills.csv", f"""
WITH af AS (SELECT filing_uuid, filing_year FROM senate_filings WHERE {AIPAC})
SELECT b.bill, count(DISTINCT b.record_key) AS aipac_filings,
       min(af.filing_year) AS first_year, max(af.filing_year) AS last_year
FROM bill_mentions b JOIN af ON af.filing_uuid = b.record_key
WHERE b.dataset='senate'
GROUP BY 1 ORDER BY aipac_filings DESC, bill""")

# 6. co-lobbyists on AIPAC's distinctive bills (<=200 clients corpus-wide)
wcsv("aipac_bill_colobbyists.csv", f"""
WITH af AS (SELECT filing_uuid FROM senate_filings WHERE {AIPAC}),
aipac_bills AS (
  SELECT DISTINCT b.bill FROM bill_mentions b JOIN af ON af.filing_uuid=b.record_key
  WHERE b.dataset='senate'),
bill_pop AS (
  SELECT b.bill, count(DISTINCT sf.client_id||'|'||sf.registrant_id) AS n_engagements
  FROM bill_mentions b JOIN senate_filings sf ON sf.filing_uuid=b.record_key
  WHERE b.dataset='senate' AND b.bill IN (SELECT bill FROM aipac_bills)
  GROUP BY 1),
distinctive AS (SELECT bill FROM bill_pop WHERE n_engagements <= 200),
co AS (
  SELECT b.bill, coalesce(e.canonical_name, sf.client_name) AS client,
         count(DISTINCT b.record_key) AS filings
  FROM bill_mentions b
  JOIN senate_filings sf ON sf.filing_uuid=b.record_key
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE b.dataset='senate' AND b.bill IN (SELECT bill FROM distinctive)
    AND upper(sf.registrant_name) NOT LIKE '%AMERICAN ISRAEL PUBLIC AFFAIRS%'
  GROUP BY 1,2)
SELECT client, count(DISTINCT bill) AS shared_distinctive_bills,
       sum(filings) AS filings_on_those_bills,
       string_agg(DISTINCT bill, '; ' ORDER BY bill) AS bills
FROM co GROUP BY 1
ORDER BY shared_distinctive_bills DESC, filings_on_those_bills DESC LIMIT 80""")

# 6b. per-bill fan-in for AIPAC's bills (how crowded is each bill)
wcsv("aipac_bills_fanin.csv", f"""
WITH af AS (SELECT filing_uuid FROM senate_filings WHERE {AIPAC}),
aipac_bills AS (
  SELECT b.bill, count(DISTINCT b.record_key) AS aipac_filings
  FROM bill_mentions b JOIN af ON af.filing_uuid=b.record_key WHERE b.dataset='senate' GROUP BY 1)
SELECT ab.bill, ab.aipac_filings,
       count(DISTINCT coalesce(e.canonical_name, sf.client_name)) AS total_clients_on_bill
FROM aipac_bills ab
JOIN bill_mentions b ON b.bill=ab.bill AND b.dataset='senate'
JOIN senate_filings sf ON sf.filing_uuid=b.record_key
LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
LEFT JOIN entities e ON e.entity_id=ea.entity_id
GROUP BY 1,2 ORDER BY total_clients_on_bill ASC, ab.aipac_filings DESC""")

# 7. Israel-policy co-lobby scan (exploratory free-text)
wcsv("israel_policy_players.csv", f"""
WITH hits AS (
  SELECT DISTINCT record_key FROM lobbying_freetext
  WHERE dataset='senate' AND regexp_matches(lower(txt), '{ISRAEL_RE}')),
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id,'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year
  FROM hits h JOIN senate_filings sf ON sf.filing_uuid=h.record_key
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL),
players AS (
  SELECT entity_id, any_value(player) AS player, count(DISTINCT filing_uuid) AS israel_filings,
         min(filing_year) AS first_year, max(filing_year) AS last_year
  FROM resolved GROUP BY 1),
spend AS (SELECT client_entity_id, round(sum(canonical_spend))::BIGINT AS total_all_issue_spend
          FROM v_client_canonical_spend GROUP BY 1)
SELECT p.player, p.israel_filings, p.first_year, p.last_year, s.total_all_issue_spend
FROM players p LEFT JOIN spend s ON s.client_entity_id=p.entity_id
WHERE p.israel_filings >= 2
ORDER BY p.israel_filings DESC LIMIT 120""")

# 8. press coupling: AIPAC quarterly amount vs Israel-topic member releases
wcsv("aipac_press_coupling.csv", f"""
WITH pr AS (
  SELECT (substr(date,1,4) || '-Q' || CAST(ceil(CAST(substr(date,6,2) AS INT)/3.0) AS INT)) AS quarter,
         count(*) AS all_releases,
         sum(CASE WHEN regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')), '{ISRAEL_RE}')
             THEN 1 ELSE 0 END) AS israel_releases
  FROM press_releases WHERE date >= '2022-01-01' GROUP BY 1),
aipac AS (
  SELECT filing_year || '-Q' || {QORD} AS quarter,
         coalesce(income, expenses)::BIGINT AS aipac_reported_amount
  FROM senate_filings WHERE {AIPAC})
SELECT pr.quarter, a.aipac_reported_amount, pr.israel_releases, pr.all_releases,
       round(100.0*pr.israel_releases/pr.all_releases, 2) AS israel_share_pct
FROM pr LEFT JOIN aipac a USING (quarter)
ORDER BY pr.quarter""")

print("\nDONE — AIPAC CSVs in", OUT)
