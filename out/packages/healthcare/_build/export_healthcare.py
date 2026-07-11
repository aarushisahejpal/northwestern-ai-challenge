"""Healthcare package exporter (2026-07-08).
Scope: senate activities coded HCR (health issues), MMM (Medicare/Medicaid),
PHA (pharmacy), MED (medical research/clinical labs). Healthcare is ALI-code-
visible (unlike crypto), so the issue-code lens is primary here.
Writes CSVs to out/packages/healthcare/data/. Run from repo root.
"""
import duckdb, csv, os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
OUT = os.path.join(REPO, "out", "packages", "healthcare", "data")
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)

CODES = "('HCR','MMM','PHA','MED')"
QORD = "CASE filing_period WHEN 'first_quarter' THEN 1 WHEN 'second_quarter' THEN 2 WHEN 'third_quarter' THEN 3 ELSE 4 END"

def wcsv(name, q):
    cur = con.execute(q)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    print(f"[csv] {name}: {len(rows)} rows")
    return cols, rows

# 0. shared CTE fragments
HC_FILINGS = f"""
hc AS (
  SELECT DISTINCT a.filing_uuid FROM senate_activities a
  WHERE a.general_issue_code IN {CODES})"""

# 1. players
_, players = wcsv("hc_players.csv", f"""
WITH {HC_FILINGS},
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id,'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year
  FROM hc JOIN senate_filings sf ON sf.filing_uuid=hc.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL AND sf.filing_type NOT LIKE 'R%'),
acts AS (
  -- activity-level share: a self-filer's single quarterly LD-2 lists dozens of
  -- issue codes, so filing-level share reads ~100% for every mega-filer;
  -- activity rows are the honest pure-play signal
  SELECT coalesce(e.entity_id,'unresolved:'||sf.client_name) AS entity_id,
         count(*) AS all_activities,
         sum(CASE WHEN a.general_issue_code IN {CODES} THEN 1 ELSE 0 END) AS health_activities
  FROM senate_filings sf
  JOIN senate_activities a ON a.filing_uuid=sf.filing_uuid
  LEFT JOIN (SELECT DISTINCT raw_name, entity_id FROM entity_aliases
             WHERE kind='client' AND dataset='senate') ea ON ea.raw_name=sf.client_name
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL AND sf.filing_type NOT LIKE 'R%'
  GROUP BY 1),
players AS (
  SELECT entity_id, any_value(player) AS player, count(DISTINCT filing_uuid) AS health_filings,
         min(filing_year) AS first_year, max(filing_year) AS last_year
  FROM resolved GROUP BY 1),
spend AS (SELECT client_entity_id, round(sum(canonical_spend))::BIGINT AS total_all_issue_spend
          FROM v_client_canonical_spend GROUP BY 1)
SELECT p.player, p.entity_id, p.health_filings,
       a.health_activities, a.all_activities,
       round(100.0*a.health_activities/a.all_activities,1) AS health_activity_share_pct,
       p.first_year, p.last_year, s.total_all_issue_spend
FROM players p
JOIN acts a USING (entity_id)
LEFT JOIN spend s ON s.client_entity_id=p.entity_id
ORDER BY s.total_all_issue_spend DESC NULLS LAST LIMIT 400""")

# 2. quarterly trend
wcsv("hc_quarterly_trend.csv", f"""
WITH {HC_FILINGS},
ded AS (
  SELECT sf.*, coalesce(e.entity_id,'unresolved:'||sf.client_name) AS ceid
  FROM senate_filings sf JOIN hc ON hc.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1),
cq AS (SELECT DISTINCT ceid, filing_year, filing_period FROM ded),
spend AS (
  SELECT cq.filing_year, cq.filing_period, round(sum(v.canonical_spend))::BIGINT AS canonical_spend_hc_clients
  FROM cq JOIN v_client_canonical_spend v
    ON v.client_entity_id=cq.ceid AND v.filing_year=cq.filing_year AND v.filing_period=cq.filing_period
  GROUP BY 1,2)
SELECT d.filing_year, d.filing_period,
       count(DISTINCT d.filing_uuid) AS health_filings,
       count(DISTINCT d.ceid) AS health_clients,
       s.canonical_spend_hc_clients
FROM ded d LEFT JOIN spend s ON s.filing_year=d.filing_year AND s.filing_period=d.filing_period
GROUP BY 1,2,s.canonical_spend_hc_clients
ORDER BY 1, {QORD.replace('filing_period','d.filing_period')}""")

# 3. per-code trend (activity counts, deduped filings)
wcsv("hc_code_trend.csv", f"""
WITH ded AS (
  SELECT sf.filing_uuid, sf.filing_year, sf.filing_period
  FROM senate_filings sf
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT d.filing_year, d.filing_period, a.general_issue_code,
       count(DISTINCT d.filing_uuid) AS filings
FROM ded d JOIN senate_activities a ON a.filing_uuid=d.filing_uuid
WHERE a.general_issue_code IN {CODES}
GROUP BY 1,2,3
ORDER BY 1, {QORD.replace('filing_period','d.filing_period')}, 3""")

# 4. registrant firms
wcsv("hc_registrant_firms.csv", f"""
WITH {HC_FILINGS},
ded AS (
  SELECT sf.* FROM senate_filings sf JOIN hc ON hc.filing_uuid=sf.filing_uuid
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT registrant_name, count(DISTINCT filing_uuid) AS health_filings,
       count(DISTINCT client_id) AS clients,
       round(sum(coalesce(income, expenses)))::BIGINT AS reported_amount_ranking_signal
FROM ded WHERE upper(trim(registrant_name)) != upper(trim(client_name))
GROUP BY 1 ORDER BY health_filings DESC LIMIT 60""")

# 5. top bills on health filings
wcsv("hc_bills.csv", f"""
WITH {HC_FILINGS}
SELECT b.bill,
       count(DISTINCT coalesce(e.canonical_name, sf.client_name)) AS clients,
       count(DISTINCT b.record_key) AS filings,
       min(sf.filing_year) AS first_year, max(sf.filing_year) AS last_year
FROM bill_mentions b
JOIN hc ON hc.filing_uuid=b.record_key
JOIN senate_filings sf ON sf.filing_uuid=b.record_key
LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
LEFT JOIN entities e ON e.entity_id=ea.entity_id
WHERE b.dataset='senate'
GROUP BY 1 ORDER BY clients DESC LIMIT 60""")

# 6. press coupling (per quarter: press HCR/MMM/PHA/MED share vs client spend)
wcsv("hc_press_coupling.csv", f"""
WITH pr AS (
  SELECT p.pr_id, (substr(p.date,1,4) || '-Q' || CAST(ceil(CAST(substr(p.date,6,2) AS INT)/3.0) AS INT)) AS quarter
  FROM press_releases p WHERE p.date >= '2022-01-01'),
tagged AS (
  SELECT DISTINCT m.pr_id FROM press_issue_mentions m WHERE m.issue_code IN {CODES}),
prq AS (
  SELECT pr.quarter, count(*) AS all_releases,
         sum(CASE WHEN t.pr_id IS NOT NULL THEN 1 ELSE 0 END) AS health_releases
  FROM pr LEFT JOIN tagged t ON t.pr_id=pr.pr_id GROUP BY 1),
{HC_FILINGS},
ded AS (
  SELECT sf.*, coalesce(e.entity_id,'unresolved:'||sf.client_name) AS ceid
  FROM senate_filings sf JOIN hc ON hc.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1),
cq AS (SELECT DISTINCT ceid, filing_year, filing_period FROM ded),
spendq AS (
  SELECT cq.filing_year || '-Q' || {QORD.replace('filing_period','cq.filing_period')} AS quarter,
         round(sum(v.canonical_spend))::BIGINT AS canonical_spend_hc_clients
  FROM cq JOIN v_client_canonical_spend v
    ON v.client_entity_id=cq.ceid AND v.filing_year=cq.filing_year AND v.filing_period=cq.filing_period
  GROUP BY 1)
SELECT prq.quarter, prq.health_releases, prq.all_releases,
       round(100.0*prq.health_releases/prq.all_releases,2) AS health_press_share_pct,
       s.canonical_spend_hc_clients
FROM prq LEFT JOIN spendq s USING (quarter)
ORDER BY prq.quarter""")

# 7. record samples for QA
wcsv("hc_record_samples_qa.csv", f"""
WITH {HC_FILINGS},
ranked AS (
  SELECT sf.client_name, sf.registrant_name, sf.filing_year, sf.filing_period,
         coalesce(sf.income, sf.expenses)::BIGINT AS amount, sf.filing_uuid,
         row_number() OVER (PARTITION BY sf.client_name ORDER BY coalesce(sf.income, sf.expenses) DESC NULLS LAST) rn,
         count(*) OVER (PARTITION BY sf.client_name) n
  FROM senate_filings sf JOIN hc ON hc.filing_uuid=sf.filing_uuid)
SELECT client_name, registrant_name, filing_year, filing_period, amount,
       filing_uuid AS show_record_key
FROM ranked WHERE rn=1 ORDER BY n DESC LIMIT 25""")

# 8. roster for the giving map: top 150 by health filings
top_by_filings = con.execute(f"""
WITH {HC_FILINGS},
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player, count(DISTINCT sf.filing_uuid) n
  FROM hc JOIN senate_filings sf ON sf.filing_uuid=hc.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL AND sf.filing_type NOT LIKE 'R%'
  GROUP BY 1 ORDER BY n DESC LIMIT 150)
SELECT player FROM resolved""").fetchall()
with open(os.path.join(REPO, "out", "healthcare_roster.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(r[0] for r in top_by_filings))
print(f"[roster] out/healthcare_roster.txt: {len(top_by_filings)} names")

print("\nDONE — healthcare CSVs in", OUT)
