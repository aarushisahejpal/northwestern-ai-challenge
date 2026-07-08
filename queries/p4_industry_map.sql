-- P4 industry map — the citeable aggregate form of skills/lead-scanner/scripts/lda_industry_map.py.
-- The script is the ergonomic front door (build the serving table, emit the entity-resolved
-- player list + roster, recall-check); these labeled blocks are what an aggregate claim cites,
-- per CLAUDE.md's "aggregate claims cite the exact SQL block + the one-command rebuild + >=3
-- sampled records" rule.
--
-- Prereqs (one-command rebuilds):
--   .venv/Scripts/python skills/lda-corpus-loader/scripts/add_lobbying_freetext.py --db db/lda_full.duckdb
--   .venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py --build-tags
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb P4 queries/p4_industry_map.sql
--
-- Demo facet = CRYPTO. lobbying_issue_mentions is the deterministic serving table (tag ->
-- exact keyword -> record_key), built from the curated industry_lexicon.json against
-- lobbying_freetext (senate activity descriptions + house specific_issues). record_key is a
-- show_record.py key (senate filing_uuid / house filing_id).
--
-- Discipline baked in (same as CLAUDE.md data-facts): senate and house are reported SEPARATELY,
-- never summed (LD-2s are filed with both chambers); v_client_canonical_spend is the P1 rollup-
-- corrected, filing_period-deduped client spend, and it is ALL-ISSUE — a ranking signal for the
-- players, not crypto-only dollars (filing-level issue attribution is imprecise).

-- ==== P4a: the premise — crypto free-text scatters across many ALI issue codes ====
-- Why issue-code filtering alone misses the industry: the crypto vocabulary appears under 15+
-- codes, well under half beneath FIN. Uses lobbying_freetext.issue_code for each tagged doc.
WITH crypto_docs AS (
  SELECT DISTINCT lim.doc_id, lf.issue_code
  FROM lobbying_issue_mentions lim
  JOIN lobbying_freetext lf USING (doc_id)
  WHERE lim.tag = 'CRYPTO')
SELECT coalesce(issue_code, '(none)') AS issue_code,
       count(*) AS crypto_docs,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_of_crypto
FROM crypto_docs GROUP BY 1 ORDER BY crypto_docs DESC LIMIT 20;

-- ==== P4b: the recall win — crypto client players a name-LIKE scan would miss ====
-- Entity-resolved crypto CLIENTS whose resolved name contains no obvious crypto term, ranked by
-- crypto-tagged filing count. These (PayPal, Visa, Robinhood, Fidelity/FMR, ...) are found ONLY
-- by what they say they lobby on. NOTE: this name regex is an illustrative subset; the tool's
-- --recall-check uses the full 43-phrase lexicon (so its count is a few players higher).
WITH crypto_clients AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag = 'CRYPTO' AND lim.dataset = 'senate'),
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         e.entity_id, sf.filing_uuid
  FROM crypto_clients c
  JOIN senate_filings sf ON sf.filing_uuid = c.filing_uuid
  LEFT JOIN entity_aliases ea
    ON ea.raw_name = sf.client_name AND ea.kind = 'client' AND ea.dataset = 'senate'
  LEFT JOIN entities e ON e.entity_id = ea.entity_id
  WHERE sf.client_name IS NOT NULL)
SELECT player, count(DISTINCT filing_uuid) AS crypto_filings
FROM resolved
WHERE NOT regexp_matches(lower(player),
  '(?i)\b(crypto|cryptocurrenc|blockchain|bitcoin|digital asset|stablecoin|defi|web3|digital currenc|coin center)\b')
GROUP BY 1 ORDER BY crypto_filings DESC LIMIT 25;

-- ==== P4c: top entity-resolved crypto client players + all-issue canonical spend ====
-- The industry, senate-side, ranked by crypto-tagged filing count, with each player's TOTAL
-- (all-issue) P1 canonical lobbying spend joined in as a size signal (NOT crypto-only dollars).
WITH crypto_clients AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag = 'CRYPTO' AND lim.dataset = 'senate'),
players AS (
  SELECT e.entity_id, coalesce(e.canonical_name, sf.client_name) AS player,
         count(DISTINCT sf.filing_uuid) AS crypto_filings,
         min(sf.filing_year) AS first_year, max(sf.filing_year) AS last_year
  FROM crypto_clients c
  JOIN senate_filings sf ON sf.filing_uuid = c.filing_uuid
  LEFT JOIN entity_aliases ea
    ON ea.raw_name = sf.client_name AND ea.kind = 'client' AND ea.dataset = 'senate'
  LEFT JOIN entities e ON e.entity_id = ea.entity_id
  WHERE sf.client_name IS NOT NULL
  GROUP BY 1, 2),
spend AS (
  SELECT client_entity_id, round(sum(canonical_spend))::BIGINT AS total_spend
  FROM v_client_canonical_spend GROUP BY 1)
SELECT p.player, p.crypto_filings, p.first_year, p.last_year, s.total_spend
FROM players p LEFT JOIN spend s ON s.client_entity_id = p.entity_id
ORDER BY p.crypto_filings DESC LIMIT 25;

-- ==== P4d: the vocabulary that found them (keyword -> distinct filings) ====
SELECT keyword, count(DISTINCT record_key) AS filings
FROM lobbying_issue_mentions WHERE tag = 'CRYPTO'
GROUP BY 1 ORDER BY filings DESC LIMIT 25;

-- ==== P4e: one player's crypto-tagged filings, with show_record.py keys (>=3 sampled) ====
-- The record-level anchor for a named player (Coinbase): the exact filings whose activity text
-- names the crypto vocabulary, each resolvable via show_record.py. Swap the client name to anchor
-- another player.
SELECT lim.record_key AS filing_uuid, lim.keyword,
       sf.filing_year, sf.filing_period, sf.income::BIGINT AS income
FROM lobbying_issue_mentions lim
JOIN senate_filings sf ON sf.filing_uuid = lim.record_key
WHERE lim.tag = 'CRYPTO' AND lim.dataset = 'senate'
  AND upper(sf.client_name) = 'COINBASE, INC.'
ORDER BY sf.income DESC NULLS LAST LIMIT 10;
