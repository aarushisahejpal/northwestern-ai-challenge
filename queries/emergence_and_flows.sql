-- Lens library: rate-of-change / emergence / contribution-flow questions the
-- point-in-time sweep_2026.sql does NOT ask. sweep ranks totals AT A MOMENT;
-- these blocks ask how an engagement CHANGED across 2022-2026 and where money
-- flows OUTSIDE the income field. Run against the full corpus:
--   .venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb E emergence_and_flows.sql
-- Conventions inherited from sweep_2026.sql: senate-primary dollar attribution;
-- dedup keyed on filing_period (constant across original+amendment), latest by
-- posted; registrations (RR/RA) excluded from quarter sums; every candidate row
-- carries a filing_uuid so it survives the named-actor rule.
-- Authored 2026-07-06 for the second full-corpus generation pass (LEDGER L020-L024).

-- Shared deduped per-engagement quarterly base is inlined per block (run_sweep
-- executes each block independently, so no cross-block temp views).

-- ==== E1: EMERGENT engagements — $0 in 2022-2023, sustained large in 2024-2025 ====
-- New lobbying relationships that appear from nothing and stick. Point-in-time
-- rankings can't see these (they're mid-pack on absolute $). Ranked by 2025 so
-- the mechanically-largest new entrant (Korea Zinc, a known takeover fight) sits
-- at the top and the more novel mid-tier sits underneath it -- read PAST row 1.
WITH q AS (
  SELECT registrant_id, client_id, registrant_name, client_name, filing_year, income
  FROM senate_filings
  WHERE filing_type NOT IN ('RR','RA')
    AND filing_period IN ('first_quarter','second_quarter','third_quarter','fourth_quarter')
    AND income IS NOT NULL
  QUALIFY row_number() OVER (PARTITION BY registrant_id, client_id, filing_year,
    filing_period ORDER BY posted DESC) = 1),
piv AS (
  SELECT registrant_id, client_id, any_value(registrant_name) rname, any_value(client_name) cname,
    sum(income) FILTER (WHERE filing_year=2022)::BIGINT y22,
    sum(income) FILTER (WHERE filing_year=2023)::BIGINT y23,
    sum(income) FILTER (WHERE filing_year=2024)::BIGINT y24,
    sum(income) FILTER (WHERE filing_year=2025)::BIGINT y25
  FROM q WHERE filing_year BETWEEN 2022 AND 2025
  GROUP BY registrant_id, client_id)
SELECT rname, cname, y24, y25
FROM piv
WHERE coalesce(y22,0)=0 AND coalesce(y23,0)=0 AND y24>=200000 AND y25>=200000
ORDER BY y25 DESC LIMIT 25;

-- ==== E2: MULTI-FIRM fan-out — registrant roster for ONE client (per-client drill) ====
-- Supports the fan-out reading of E1/F1 leads: does a client mobilize MANY firms
-- at once? Deliberately per-client (edit the ILIKE), NOT a global ranking. A
-- global "firms per client" sweep is unreliable here because client identity
-- FRAGMENTS across registrants: Senate client_id is registrant-scoped (CLAUDE.md),
-- and BOTH the entity resolver and simple name-normalization split these names
-- (Vantive -> {VANTIVE, INC. / Vantive US Healthcare LLC / VANTIVE HEALTH LLC};
--  TP-Link -> 3 entity_ids incl. one mis-parsed "Akin Gump ... on behalf of ...").
-- So the honest firm-count is read from the roster below, per client, by eye --
-- not trusted from a fragile GROUP BY. Worked example: Vantive = six firms in 2025.
WITH q AS (
  SELECT registrant_name, registrant_id, client_name, filing_year, filing_period,
         income::BIGINT income, filing_uuid
  FROM senate_filings
  WHERE client_name ILIKE '%VANTIVE%'          -- <-- edit this to drill another client
    AND filing_type NOT IN ('RR','RA')
    AND filing_period IN ('first_quarter','second_quarter','third_quarter','fourth_quarter')
  QUALIFY row_number() OVER (PARTITION BY registrant_id, client_name, filing_year,
    filing_period ORDER BY posted DESC) = 1)
SELECT registrant_name,
       count(DISTINCT filing_year || filing_period) n_quarters,
       sum(income) FILTER (WHERE filing_year=2025)::BIGINT y25_income,
       min(filing_year || ' ' || filing_period) first_seen,
       any_value(filing_uuid) sample_uuid
FROM q GROUP BY registrant_name
ORDER BY y25_income DESC NULLS LAST;

-- ==== E3: INDIVIDUALS lobbying as clients (client_description = 'Individual') ====
-- A named person -- not a company -- retaining a firm. Structurally invisible to
-- spend rankings (an individual never tops them), but a person paying six figures
-- to lobby on their own behalf is inherently a story. Surfaces Scott Sheffield.
SELECT f.client_name, f.registrant_name,
       sum(f.income) FILTER (WHERE f.filing_year=2024)::BIGINT y24,
       sum(f.income) FILTER (WHERE f.filing_year=2025)::BIGINT y25,
       string_agg(DISTINCT a.general_issue_code, ',') issue_codes,
       any_value(a.description) sample_issue
FROM senate_filings f
LEFT JOIN senate_activities a USING (filing_uuid)
WHERE lower(trim(f.client_description)) = 'individual'
  AND f.filing_type NOT IN ('RR','RA')
  AND f.filing_period IN ('first_quarter','second_quarter','third_quarter','fourth_quarter')
GROUP BY f.client_name, f.registrant_name
HAVING sum(f.income) FILTER (WHERE f.filing_year IN (2024,2025)) >= 200000
ORDER BY (coalesce(sum(f.income) FILTER (WHERE f.filing_year=2024),0)
        + coalesce(sum(f.income) FILTER (WHERE f.filing_year=2025),0)) DESC LIMIT 25;

-- ==== E4: SINGLE-QUARTER income spikes on established engagements (data-quality/event) ====
-- One quarter >= 6x the engagement's own median and >= $400K, on an engagement
-- with >= 6 quarters of history. Some are real one-off surges; many are LD-2
-- misreporting (a cumulative/annual figure typed into one quarter). Complements
-- sweep S5, which only flags income GAPS (nulls), never overstatements.
WITH q AS (
  SELECT registrant_id, client_id, registrant_name, client_name, filing_year, filing_period, income
  FROM senate_filings
  WHERE filing_type NOT IN ('RR','RA') AND income IS NOT NULL
    AND filing_period IN ('first_quarter','second_quarter','third_quarter','fourth_quarter')
  QUALIFY row_number() OVER (PARTITION BY registrant_id, client_id, filing_year,
    filing_period ORDER BY posted DESC) = 1),
stats AS (
  SELECT registrant_id, client_id, any_value(registrant_name) rn, any_value(client_name) cn,
         count(*) nq, median(income) med, max(income) mx
  FROM q GROUP BY registrant_id, client_id
  HAVING count(*) >= 6 AND median(income) > 0)
SELECT s.rn, s.cn, s.nq, s.med::BIGINT median_q, s.mx::BIGINT peak_q,
       round(s.mx / s.med, 1) x_over_median,
       (SELECT filing_year || ' ' || filing_period FROM q e
        WHERE e.registrant_id=s.registrant_id AND e.client_id=s.client_id
        ORDER BY income DESC LIMIT 1) peak_period
FROM stats s
WHERE s.mx >= 400000 AND s.mx >= 6 * s.med
ORDER BY x_over_median DESC LIMIT 20;

-- ==== F1: contribution-flow concentration — LD-203 dollars aimed at ONE honoree ====
-- sweep S4 ranks honorees by total, which mixes every giver together. This flips
-- it: which single registrant pours >=75% of its honoree dollars into ONE named
-- honoree, at >= $40K. Surfaces very large single "honorary" payments -- e.g.
-- Vantive's $2.5M to the White House Ballroom Project -- that a total-by-honoree
-- ranking dilutes. Read past the mechanical top rows (union N/A placeholders).
WITH c AS (
  SELECT ci.honoree, con.registrant_name, ci.payee,
         sum(ci.amount) amt, count(*) n, min(ci.date) first_date
  FROM senate_contribution_items ci JOIN senate_contributions con USING (filing_uuid)
  WHERE ci.honoree IS NOT NULL AND trim(ci.honoree) <> ''
    AND con.filing_year IN (2024, 2025)
  GROUP BY 1, 2, 3),
tot AS (SELECT registrant_name, sum(amt) reg_tot FROM c GROUP BY 1)
SELECT c.registrant_name, c.honoree, c.payee, c.amt::BIGINT to_honoree,
       round(c.amt / t.reg_tot, 2) concentration, c.n items, c.first_date
FROM c JOIN tot t USING (registrant_name)
WHERE t.reg_tot >= 60000 AND c.amt >= 40000 AND c.amt / t.reg_tot >= 0.75
ORDER BY c.amt DESC LIMIT 25;
