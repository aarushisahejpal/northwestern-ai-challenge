-- L006: UAE sovereign wealth (Mubadala family) behind US lobbying engagements.
-- Requires entity tables (skills/lda-entity-resolver/scripts/resolve_entities.py).
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_pilot.duckdb L006 queries/l006_mubadala.sql
-- OUTSIDE DATA used alongside these blocks (disclosed in README §4): FARA bulk
-- FARA_All_ForeignPrincipals.csv (efile.fara.gov/bulk, fetched 2026-07-06) — zero
-- Mubadala-family FARA registrations ever; ADIA's six all terminated by 2022.

-- ==== L006a: all AE-country foreign entities, resolved, pilot corpus (2025+2026Q1) ====
SELECT ea.norm_key AS resolved_entity, count(DISTINCT fe.filing_uuid) AS filings,
       count(DISTINCT f.client_name) AS clients,
       string_agg(DISTINCT f.client_name, ' | ') AS client_names,
       min(fe.filing_uuid) AS sample_uuid
FROM senate_foreign_entities fe
JOIN senate_filings f USING (filing_uuid)
JOIN entity_aliases ea ON ea.kind = 'foreign_entity' AND ea.raw_name = fe.name
WHERE fe.country = 'AE'
GROUP BY 1 ORDER BY filings DESC;

-- ==== L006b: the Mubadala family — every engagement, with activity text ====
-- MTI INVESTMENT COMPANY is included: DIPRA-style parenthetical text in the raw
-- names ("MTI ... (OWNS 21% OF GLOBALFOUNDRIES)") identifies it as Mubadala
-- Technology Investment; treat as family member, flag for outside-data confirm.
WITH fam AS (
  SELECT DISTINCT fe.filing_uuid, fe.name AS raw_foreign_entity
  FROM senate_foreign_entities fe
  WHERE upper(fe.name) LIKE '%MUBADALA%' OR upper(fe.name) LIKE 'MTI INVESTMENT%')
SELECT f.filing_year, f.filing_type, f.client_name, f.registrant_name,
       f.income::BIGINT AS income, fam.raw_foreign_entity,
       a.general_issue_code AS code, substr(a.description, 1, 120) AS activity_start,
       f.filing_uuid
FROM fam
JOIN senate_filings f USING (filing_uuid)
LEFT JOIN senate_activities a USING (filing_uuid)
ORDER BY f.filing_year, f.client_name, f.filing_type;

-- ==== L006c: house-side confirmation for Mubadala-linked engagements ====
SELECT x.senate_registrant_name, x.senate_client_name,
       x.n_senate_filings, x.n_house_filings,
       x.sample_senate_uuid, x.sample_house_filing_id
FROM registrant_crosswalk x
WHERE (x.senate_registrant_id, x.senate_client_id) IN (
  SELECT DISTINCT f.registrant_id, f.client_id
  FROM senate_foreign_entities fe JOIN senate_filings f USING (filing_uuid)
  WHERE upper(fe.name) LIKE '%MUBADALA%' OR upper(fe.name) LIKE 'MTI INVESTMENT%')
ORDER BY x.n_house_filings DESC;
