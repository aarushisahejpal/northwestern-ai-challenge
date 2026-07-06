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
