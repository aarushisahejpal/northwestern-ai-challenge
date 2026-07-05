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
