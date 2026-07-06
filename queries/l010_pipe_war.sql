-- L010: the pipe-materials war — DIPRA's $540K quarter vs a fragmented opposition.
-- Descends from L004 (see queries/l004_quiet_bills.sql blocks L004h/i/k).
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_2026.duckdb L010 queries/l010_pipe_war.sql

-- ==== L010a: iron-side ecosystem — do DIPRA's likely members lobby directly? ====
SELECT f.client_name, f.registrant_name, f.income::BIGINT AS income,
       f.expenses::BIGINT AS expenses, f.filing_type, f.filing_uuid
FROM senate_filings f
WHERE upper(f.client_name) LIKE '%MCWANE%'
   OR upper(f.client_name) LIKE '%U.S. PIPE%' OR upper(f.client_name) LIKE '%US PIPE%'
   OR upper(f.client_name) LIKE '%CAST IRON%'
   OR upper(f.client_name) LIKE '%AMERICAN IRON%'
   OR upper(f.registrant_name) LIKE '%MCWANE%'
ORDER BY coalesce(f.income, f.expenses) DESC NULLS LAST;

-- ==== L010b: all activity text mentioning pipe materials / domestic sourcing of pipe ====
SELECT f.client_name, f.registrant_name, f.income::BIGINT AS income,
       a.general_issue_code AS code,
       substr(a.description, 1, 160) AS description_start, f.filing_uuid
FROM senate_activities a JOIN senate_filings f USING (filing_uuid)
WHERE a.description ILIKE '%ductile%' OR a.description ILIKE '%iron pipe%'
   OR (a.description ILIKE '%materials provision%')
ORDER BY f.income DESC NULLS LAST
LIMIT 20;

-- ==== L010c: DIPRA + McWane quarterly spend, 2025 full year vs 2026-Q1 (pilot DB only) ====
-- Is DIPRA's $540K Q1-2026 filing (uuid 7e61b5d2) a spike or business as usual?
-- NOTE: filing_period is a spelled-out label ("first_quarter"..), NOT 'Q1'..'Q4' --
-- filing_type carries the Q1-Q4(Y) code (verified 2026-07-05: 'Q1Y' = "Report,
-- No Activity", a distinct filing subtype, not a duplicate of 'Q1'; DIPRA/McWane
-- have no 1A/2A-style amendments in this window so no cross-subtype dedup needed).
-- Dedup per H1b pattern: drops literal same-report re-posts (org+client+year+type).
WITH s AS (
  SELECT upper(trim(registrant_name)) AS org, upper(trim(client_name)) AS client,
         filing_year AS yr, filing_type AS qcode, income, filing_uuid, posted
  FROM senate_filings
  WHERE (upper(client_name) LIKE '%DIPRA%'
      OR upper(client_name) LIKE '%DUCTILE IRON PIPE%'
      OR upper(client_name) LIKE '%MCWANE%')
    AND filing_type LIKE 'Q%'
    AND (filing_year = 2025 OR (filing_year = 2026 AND filing_type LIKE 'Q1%'))
  QUALIFY row_number() OVER (PARTITION BY org, client, yr, qcode
    ORDER BY posted DESC) = 1)
SELECT client, org, yr, qcode, income::BIGINT AS income, filing_uuid
FROM s
ORDER BY client, yr, qcode;

-- ==== L010d: opposing coalition (plastic/copper pipe), Q1 2026 spend (pilot DB) ====
SELECT client_name, registrant_name, income::BIGINT AS income, filing_uuid
FROM senate_filings
WHERE filing_year = 2026 AND filing_type = 'Q1'
  AND (upper(client_name) LIKE '%PLASTICS INDUSTRY%' OR upper(client_name) LIKE '%DIAMOND PLASTIC%'
       OR upper(client_name) LIKE '%HOBAS%' OR upper(client_name) LIKE '%COPPER DEVELOPMENT%')
ORDER BY client_name, registrant_name;
