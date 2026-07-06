-- Lens sweep: the data manual's recommended starting-point questions, run
-- against the 2026-Q1 corpus (db/lda_2026.duckdb). Each block is one question.
-- Results that become ledger leads cite this file plus the block label.
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_2026.duckdb

-- ==== S1a: biggest spenders by client (Senate, 2026 Q1) ====
SELECT client_name, sum(income)::BIGINT AS total_income, count(*) AS filings
FROM senate_filings WHERE income IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC LIMIT 15;

-- ==== S1b: most-active registrants ====
SELECT registrant_name, count(*) AS filings,
       count(DISTINCT client_name) AS clients, sum(income)::BIGINT AS total_income
FROM senate_filings GROUP BY 1 ORDER BY filings DESC LIMIT 15;

-- ==== S1c: busiest issue codes ====
SELECT a.general_issue_code, count(DISTINCT a.filing_uuid) AS filings,
       sum(f.income)::BIGINT AS attributed_income
FROM senate_activities a JOIN senate_filings f USING (filing_uuid)
GROUP BY 1 ORDER BY filings DESC LIMIT 15;

-- ==== S2a: revolving door — ex-congressional staff registering to lobby in 2026 ====
-- New registrations (RR) whose lobbyists list covered positions in Congress.
SELECT f.registrant_name, f.client_name, l.first_name, l.last_name,
       l.covered_position, f.filing_uuid
FROM senate_lobbyists l JOIN senate_filings f USING (filing_uuid)
WHERE f.filing_type = 'RR'
  AND (l.covered_position ILIKE '%senat%' OR l.covered_position ILIKE '%congress%'
       OR l.covered_position ILIKE '%rep.%' OR l.covered_position ILIKE '%house%'
       OR l.covered_position ILIKE '%chief of staff%')
ORDER BY f.registrant_name LIMIT 40;

-- ==== S2b: revolving door — most-named offices in covered positions ====
SELECT covered_position, count(*) AS n
FROM v_covered_positions GROUP BY 1 ORDER BY n DESC LIMIT 20;

-- ==== S3: foreign influence — foreign entities behind 2026 lobbying ====
SELECT fe.country, fe.name AS foreign_entity, f.client_name, f.registrant_name,
       f.filing_uuid
FROM senate_foreign_entities fe JOIN senate_filings f USING (filing_uuid)
ORDER BY fe.country LIMIT 40;

-- ==== S4: contribution flows — honorees in what exists of 2026 LD-203s ====
SELECT honoree, count(*) AS items, sum(amount)::BIGINT AS total,
       string_agg(DISTINCT contributor_name, '; ') AS contributors
FROM senate_contribution_items WHERE honoree IS NOT NULL
GROUP BY 1 ORDER BY total DESC NULLS LAST LIMIT 20;

-- ==== S5: data-quality — registrants with systematic income gaps ====
SELECT registrant_name, count(*) AS filings,
       sum(CASE WHEN income IS NULL AND expenses IS NULL THEN 1 ELSE 0 END) AS no_money_disclosed
FROM senate_filings
WHERE filing_type <> 'RR'
GROUP BY 1 HAVING count(*) >= 5
ORDER BY no_money_disclosed * 1.0 / filings DESC, filings DESC LIMIT 15;

-- ==== H1: Senate<->House reconciliation — same org+client, different income (Q1 2026) ====
WITH s AS (
  SELECT upper(trim(registrant_name)) AS org, upper(trim(client_name)) AS client,
         sum(income) AS s_income
  FROM senate_filings
  WHERE filing_year = 2026 AND filing_type LIKE 'Q1%' GROUP BY 1, 2),
h AS (
  SELECT upper(trim(organization_name)) AS org, upper(trim(client_name)) AS client,
         sum(income) AS h_income
  FROM house_filings WHERE report_period = 'Q1' GROUP BY 1, 2)
SELECT s.org, s.client, s.s_income::BIGINT AS senate_income,
       h.h_income::BIGINT AS house_income,
       (s.s_income - h.h_income)::BIGINT AS delta
FROM s JOIN h USING (org, client)
WHERE s.s_income IS NOT NULL AND h.h_income IS NOT NULL
  AND abs(coalesce(s.s_income, 0) - coalesce(h.h_income, 0)) > 5000
ORDER BY abs(s.s_income - h.h_income) DESC LIMIT 20;

-- ==== H2 / C1: bills lobbied AND pressed — the say-vs-pay bridge (Q1 2026) ====
WITH lobbied AS (
  SELECT bill, count(*) AS lobby_mentions FROM bill_mentions
  WHERE dataset IN ('senate', 'house') GROUP BY 1),
pressed AS (
  SELECT bill, count(*) AS press_mentions FROM bill_mentions
  WHERE dataset = 'press' GROUP BY 1)
SELECT bill, lobby_mentions, press_mentions
FROM lobbied JOIN pressed USING (bill)
ORDER BY lobby_mentions * press_mentions DESC LIMIT 20;

-- ==== P3: member press-activity outliers (releases/month vs corpus norm) ====
SELECT bioguide_id, name, month, n_releases
FROM v_releases_by_member_month
WHERE n_releases > 40 ORDER BY n_releases DESC LIMIT 15;

-- ==== H1b: reconciliation with amendment/duplicate dedup (supersedes H1) ====
-- L001 artifact check (2026-07-04) proved raw sums double-count: registrants file
-- duplicates (S-3 Group filed identical Senate Q1s 22s apart) and amendments
-- (Senate filing_type '1A'; House refilings under new filing_ids). Keep only the
-- latest filing per org+client+period on BOTH sides.
WITH s AS (
  SELECT upper(trim(registrant_name)) AS org, upper(trim(client_name)) AS client, income
  FROM senate_filings
  WHERE filing_year = 2026 AND (filing_type LIKE 'Q1%' OR filing_type = '1A')
  QUALIFY row_number() OVER (PARTITION BY upper(trim(registrant_name)),
    upper(trim(client_name)), filing_period ORDER BY posted DESC) = 1),
h AS (
  SELECT upper(trim(organization_name)) AS org, upper(trim(client_name)) AS client, income
  FROM house_filings WHERE report_period = 'Q1'
  QUALIFY row_number() OVER (PARTITION BY upper(trim(organization_name)),
    upper(trim(client_name)), report_period ORDER BY CAST(filing_id AS BIGINT) DESC) = 1)
SELECT s.org, s.client, s.income::BIGINT AS senate_income, h.income::BIGINT AS house_income,
       (s.income - h.income)::BIGINT AS delta
FROM s JOIN h USING (org, client)
WHERE s.income IS NOT NULL AND h.income IS NOT NULL AND abs(s.income - h.income) > 5000
ORDER BY abs(s.income - h.income) DESC LIMIT 20;

-- ==== H1c: reconciliation joined on registrant+client IDs (supersedes H1b's name join) ====
-- Verified 2026-07-06: house <senateID> is the compound key
-- "<senate_registrant_id>-<senate_client_id>" (55,627 house rows match a senate pair
-- exactly; sampled pairs agree on names). Joining on IDs instead of upper(trim(name))
-- catches engagements the name join missed (casing/punctuation/dba variants) and
-- can't false-match distinct same-named orgs. Dedup per H1b on both sides. Senate
-- filing_period is spelled out ("first_quarter"); filing_type carries Q1..Q4 codes.
WITH s AS (
  SELECT registrant_id, client_id, filing_year, filing_type AS q, income,
         registrant_name, client_name, filing_uuid
  FROM senate_filings
  WHERE filing_type LIKE 'Q%'
  QUALIFY row_number() OVER (PARTITION BY registrant_id, client_id, filing_year,
    filing_type ORDER BY posted DESC) = 1),
h AS (
  SELECT split_part(senate_reg_id, '-', 1) AS registrant_id,
         split_part(senate_reg_id, '-', 2) AS client_id,
         report_year AS filing_year,
         'Q' || substr(report_period, 2, 1) AS q, income, filing_id
  FROM house_filings
  WHERE senate_reg_id LIKE '%-%' AND report_period LIKE 'Q%'
  QUALIFY row_number() OVER (PARTITION BY senate_reg_id, report_year, report_period
    ORDER BY CAST(filing_id AS BIGINT) DESC) = 1)
SELECT s.registrant_name, s.client_name, s.filing_year, s.q,
       s.income::BIGINT AS senate_income, h.income::BIGINT AS house_income,
       (s.income - h.income)::BIGINT AS delta, s.filing_uuid, h.filing_id
FROM s JOIN h USING (registrant_id, client_id, filing_year, q)
WHERE s.income IS NOT NULL AND h.income IS NOT NULL
  AND abs(s.income - h.income) > 5000
ORDER BY abs(s.income - h.income) DESC LIMIT 25;

-- ==== H1d: chronic cross-chamber mis-reporters (L001 revisit; needs H1c's ID join) ====
-- Aggregates H1c's engagement-quarter deltas by registrant. exact_10x counts
-- quarters where one side is exactly 10x the other (missing/extra-zero data entry).
WITH s AS (
  SELECT registrant_id, client_id, filing_year, filing_type AS q, income,
         registrant_name
  FROM senate_filings WHERE filing_type LIKE 'Q%'
  QUALIFY row_number() OVER (PARTITION BY registrant_id, client_id, filing_year,
    filing_type ORDER BY posted DESC) = 1),
h AS (
  SELECT split_part(senate_reg_id, '-', 1) AS registrant_id,
         split_part(senate_reg_id, '-', 2) AS client_id,
         report_year AS filing_year, 'Q' || substr(report_period, 2, 1) AS q, income
  FROM house_filings
  WHERE senate_reg_id LIKE '%-%' AND report_period LIKE 'Q%'
  QUALIFY row_number() OVER (PARTITION BY senate_reg_id, report_year, report_period
    ORDER BY CAST(filing_id AS BIGINT) DESC) = 1),
j AS (
  SELECT s.registrant_name, s.income AS si, h.income AS hi
  FROM s JOIN h USING (registrant_id, client_id, filing_year, q)
  WHERE s.income IS NOT NULL AND h.income IS NOT NULL)
SELECT registrant_name,
       count(*) AS matched_qtrs,
       sum(CASE WHEN abs(si - hi) > 5000 THEN 1 ELSE 0 END) AS mismatched,
       sum(CASE WHEN si = 10 * hi OR hi = 10 * si THEN 1 ELSE 0 END) AS exact_10x,
       sum(abs(si - hi))::BIGINT AS total_abs_delta
FROM j GROUP BY 1
HAVING sum(CASE WHEN abs(si - hi) > 5000 THEN 1 ELSE 0 END) >= 3
ORDER BY mismatched DESC, total_abs_delta DESC LIMIT 20;

-- ==== S1d: top spenders by RESOLVED client entity (needs entity tables) ====
-- Raw S1a fragments clients across name variants; this groups by norm_key.
SELECT e.canonical_name, sum(f.income)::BIGINT AS total_income,
       count(*) AS filings, count(DISTINCT f.client_name) AS name_variants
FROM senate_filings f
JOIN entity_aliases ea ON ea.kind = 'client' AND ea.dataset = 'senate'
                       AND ea.raw_name = f.client_name
JOIN entities e ON e.entity_id = ea.entity_id
WHERE f.income IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC LIMIT 15;

-- ==== C1b: say-vs-pay weighted by dollars (supersedes mention counts) ====
-- Caveat: income is filing-level; a filing naming several bills attributes its
-- full income to each. Use for ranking, not exact dollars.
WITH m AS (SELECT DISTINCT bill, dataset, record_key FROM bill_mentions
           WHERE dataset IN ('senate', 'house')),
lob AS (
  SELECT m.bill, count(*) AS n_filings,
         sum(coalesce(sf.income, hf.income, 0))::BIGINT AS attributed_dollars
  FROM m LEFT JOIN senate_filings sf ON m.dataset = 'senate' AND m.record_key = sf.filing_uuid
         LEFT JOIN house_filings hf ON m.dataset = 'house' AND m.record_key = hf.filing_id
  GROUP BY 1),
p AS (SELECT bill, count(*) AS press_mentions FROM bill_mentions
      WHERE dataset = 'press' GROUP BY 1)
SELECT lob.bill, n_filings, attributed_dollars, coalesce(press_mentions, 0) AS press_mentions
FROM lob LEFT JOIN p ON lob.bill = p.bill
ORDER BY attributed_dollars DESC LIMIT 25;
