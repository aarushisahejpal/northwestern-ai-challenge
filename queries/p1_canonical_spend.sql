-- P1 — Canonical client spend (rollup double-count correction)
-- =============================================================================
-- Companion to the `v_client_canonical_spend` VIEW built by
-- skills/lda-entity-resolver/scripts/resolve_entities.py (single source of the view
-- DDL — see CANONICAL_SPEND_VIEW there). Prereq: build the DB (lda-corpus-loader)
-- then run resolve_entities.py, which materializes the view. These blocks are the
-- cited demo + QA for the aggregate-claim rule (exact SQL + one-command rebuild +
-- sampled records).
--
-- The problem (from the corpus data-cleanup notes): a client that lobbies in-house
-- files as its OWN registrant (registrant name == client name) and reports its TOTAL
-- lobbying spend. Outside firms that same client hires ALSO file, reporting the income
-- they received from it — money already inside the in-house total. So summing every
-- filing for a client double-counts. Not universal: some clients self-file, some don't.
--
-- The rule (per client, per quarter):
--   amount(row)      = greatest(coalesce(income,0), coalesce(expenses,0))   -- reported $,
--                      whichever field is populated (in-house filers sometimes use income)
--   self_filed(row)  = norm_key(registrant) == norm_key(client)            -- in-house
--   inhouse_amount   = sum(amount) where self_filed
--   outside_amount   = sum(amount) where NOT self_filed
--   canonical_spend  = greatest(inhouse_amount, outside_amount)   -- NEVER the sum
--   double_count_delta = least(inhouse_amount, outside_amount)    -- what naive over-adds
-- Amendments deduped on filing_period (latest by posted), per sweep_2026.sql#H1c.
-- Senate-only (completeness-primary; never sum senate+house). Prior art / cross-check:
-- the team's lobbyR `flag_client_registrant_conflict()` / `flag_dupes()` (README §4).
--
-- Corpus scale (2025, db/lda_full.duckdb): naive client-level sum ≈ $6.23B vs
-- canonical ≈ $5.46B — ~12.3% ($766M) of apparent spend is in-house double-count.
-- =============================================================================

-- #P1a — American Express: the motivating case. In-house 'American Express Company'
-- reports the total; Akin Gump / Rich Feuer income for it is already inside that total.
SELECT client_name, filing_year, filing_period,
       inhouse_amount, outside_amount, canonical_spend, naive_sum_all, method
FROM v_client_canonical_spend
WHERE client_norm_key = 'AMERICAN EXPRESS'
ORDER BY filing_year, filing_period;

-- #P1b — Edge case that keys-on-`expenses`-only gets WRONG: a self-filer that reports
-- its total under `income`, not `expenses` (AIPAC). Canonical must still be the real
-- figure, not $0. This is why `amount` uses greatest(income, expenses).
SELECT client_name, filing_year, filing_period,
       inhouse_amount, outside_amount, canonical_spend, method
FROM v_client_canonical_spend
WHERE client_norm_key = 'AMERICAN ISRAEL PUBLIC AFFAIRS COMMITTEE'
ORDER BY filing_year, filing_period;

-- #P1c — Biggest rollup double-counts (where naive summing most overstates a client).
-- These are exactly the "biggest spender by client" leads most exposed to a Stage-1
-- refutation if cited from a naive sum.
SELECT client_name, filing_year, sum(double_count_delta) AS delta,
       sum(canonical_spend) AS canonical, sum(naive_sum_all) AS naive_sum_all
FROM v_client_canonical_spend
WHERE filing_year = 2025 AND has_inhouse_filing
GROUP BY client_name, filing_year
HAVING delta > 0
ORDER BY delta DESC
LIMIT 15;

-- #P1d — Lead QA: does an existing lead's spend change under the correction?
--   L023 Vantive US Healthcare self-files -> canonical is ~$120-240k/qtr below naive
--     (its fan-out figures need this correction).
--   L020 TP-Link and L024 BATT have NO in-house filing -> unaffected, figures stand.
SELECT client_name, filing_year, filing_period,
       canonical_spend, naive_sum_all, double_count_delta, method
FROM v_client_canonical_spend
WHERE client_norm_key LIKE 'VANTIVE US HEALTHCARE%'
   OR client_norm_key LIKE 'TP LINK SYSTEMS%'
   OR client_norm_key LIKE '%BATTERY ADVOCACY FOR TECHNOLOGY TRANSFORMATION%'
ORDER BY client_norm_key, filing_year, filing_period;

-- #P1e — Corpus-wide magnitude of the correction, by year.
SELECT filing_year,
       sum(naive_sum_all)   AS naive_sum_all,
       sum(canonical_spend) AS canonical,
       sum(double_count_delta) AS double_count_removed,
       round(100.0 * sum(double_count_delta) / nullif(sum(naive_sum_all), 0), 1) AS pct_removed
FROM v_client_canonical_spend
GROUP BY filing_year
ORDER BY filing_year;
