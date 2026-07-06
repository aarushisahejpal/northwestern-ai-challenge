-- L003: opaque entities each paying ~$1M for lobbying in a single quarter.
-- From sweep#S1a: Innovairrs & Co., Five Rivers Conservation Group LLC,
-- Fay Law Group, Coretsu Inc. Who are they, who did they hire, for what?
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_2026.duckdb L003 queries/l003_opaque_spenders.sql

-- ==== L003a: every filing touching the four entities (either role) ====
SELECT client_name, registrant_name, filing_type, income::BIGINT AS income,
       expenses::BIGINT AS expenses, client_state, client_description,
       substr(posted, 1, 10) AS posted, filing_uuid
FROM senate_filings
WHERE upper(client_name) LIKE '%INNOVAIRRS%' OR upper(registrant_name) LIKE '%INNOVAIRRS%'
   OR upper(client_name) LIKE '%FIVE RIVERS CONSERVATION%' OR upper(registrant_name) LIKE '%FIVE RIVERS CONSERVATION%'
   OR upper(client_name) LIKE '%FAY LAW%' OR upper(registrant_name) LIKE '%FAY LAW%'
   OR upper(client_name) LIKE '%CORETSU%' OR upper(registrant_name) LIKE '%CORETSU%'
ORDER BY client_name, posted;

-- ==== L003c: registrant context — full client books of Checkmate and Jake Perry ====
SELECT registrant_name, client_name, filing_type, income::BIGINT AS income,
       substr(posted, 1, 10) AS posted, filing_uuid
FROM senate_filings
WHERE upper(registrant_name) LIKE '%CHECKMATE GOVERNMENT%'
   OR upper(registrant_name) LIKE '%JAKE PERRY%'
ORDER BY registrant_name, income DESC NULLS LAST;

-- ==== L003b: what they lobby on — issue codes and activity text ====
SELECT f.client_name, a.general_issue_code AS code,
       substr(a.description, 1, 120) AS description_start, f.filing_uuid
FROM senate_activities a JOIN senate_filings f USING (filing_uuid)
WHERE upper(f.client_name) LIKE '%INNOVAIRRS%'
   OR upper(f.client_name) LIKE '%FIVE RIVERS CONSERVATION%'
   OR upper(f.client_name) LIKE '%FAY LAW%'
   OR upper(f.client_name) LIKE '%CORETSU%'
ORDER BY f.client_name;
