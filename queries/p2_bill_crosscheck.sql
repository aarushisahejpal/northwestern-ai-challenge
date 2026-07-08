-- P2 bill cross-check — the citeable aggregate form of skills/lead-scanner/scripts/lda_bill_lookup.py.
-- The script is the ergonomic front door (number OR alias, all datasets, sample keys);
-- these labeled blocks are what an aggregate claim cites, per CLAUDE.md's "aggregate
-- claims cite the exact SQL block + the one-command rebuild + >=3 sampled records" rule.
--
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb P2 queries/p2_bill_crosscheck.sql
-- Demo bill = HR5376 (Inflation Reduction Act). To cross-check a different bill, swap the
-- two literals: the normalized number ('HR5376', per build_db.py norm_bill) and, for the
-- name side, the alias's precise phrase ('inflation reduction act') from bill_aliases.json.
-- For a PHRASE-PRIMARY bill (Farm Bill: no reliable number — H.R.2 is reused every Congress),
-- use P2d, which name-matches filing free-text instead of the number.
--
-- Discipline baked in (same as CLAUDE.md data-facts): senate is amendment/duplicate-deduped
-- on filing_period (NOT filing_type); senate and house are reported SEPARATELY, never summed
-- (LD-2s are filed with both chambers); attributed income is FILING-LEVEL (a filing naming
-- several bills attributes its full income to each) — a ranking signal, not exact dollars.

-- ==== P2a: cross-dataset touch counts for HR5376 (who cites the number vs names it) ====
WITH num AS (
  SELECT dataset, count(DISTINCT record_key) AS filings_or_releases
  FROM bill_mentions WHERE bill = 'HR5376' GROUP BY 1),
name_press AS (
  SELECT count(*) AS n FROM press_releases
  WHERE regexp_matches(text, '(?i)\binflation reduction act\b'))
SELECT 'senate: cite number' AS signal,
       (SELECT filings_or_releases FROM num WHERE dataset = 'senate') AS n
UNION ALL SELECT 'house: cite number',
       (SELECT filings_or_releases FROM num WHERE dataset = 'house')
UNION ALL SELECT 'press: cite number',
       (SELECT coalesce(filings_or_releases, 0) FROM num WHERE dataset = 'press')
UNION ALL SELECT 'press: NAME the bill (say-vs-pay bridge)', (SELECT n FROM name_press);

-- ==== P2b: senate top clients behind HR5376 — deduped engagement-quarters, ranked ====
WITH keys AS (
  SELECT DISTINCT record_key FROM bill_mentions
  WHERE dataset = 'senate' AND bill = 'HR5376'),
f AS (
  SELECT sf.filing_uuid, sf.registrant_name, sf.client_name, sf.income,
         sf.filing_year, sf.filing_period
  FROM senate_filings sf JOIN keys ON sf.filing_uuid = keys.record_key
  QUALIFY row_number() OVER (
    PARTITION BY upper(trim(sf.registrant_name)), upper(trim(sf.client_name)),
                 sf.filing_year, sf.filing_period
    ORDER BY sf.posted DESC) = 1)
SELECT client_name, sum(income)::BIGINT AS attributed_income, count(*) AS filings
FROM f GROUP BY 1 ORDER BY attributed_income DESC NULLS LAST LIMIT 15;

-- ==== P2c: press say-vs-pay for HR5376 — number-cited vs name-only ====
-- The name-only count is the coverage a number-only match (the L004 trap) would miss.
WITH num AS (
  SELECT DISTINCT src_file || ':' || src_line AS k FROM press_releases pr
  JOIN bill_mentions bm ON bm.record_key = pr.src_file || ':' || pr.src_line
  WHERE bm.dataset = 'press' AND bm.bill = 'HR5376'),
nm AS (
  SELECT DISTINCT src_file || ':' || src_line AS k FROM press_releases
  WHERE regexp_matches(text, '(?i)\binflation reduction act\b'))
SELECT (SELECT count(*) FROM num) AS cite_number,
       (SELECT count(*) FROM nm) AS name_it,
       (SELECT count(*) FROM nm WHERE k NOT IN (SELECT k FROM num)) AS name_only;

-- ==== P2d: phrase-primary path (Farm Bill) — name-matched filing free-text ====
-- No reliable number (H.R.2 is reassigned each Congress), so the filing-side signal is the
-- filers' own free-text (senate activity descriptions, house specific_issues). All rows keep
-- a show_record.py-resolvable key (senate filing_uuid / house filing_id).
-- Phrase set mirrors bill_aliases.json farm-bill.phrases so counts match lda_bill_lookup.py.
SELECT 'senate: activity text names it' AS signal,
       count(DISTINCT filing_uuid) AS filings
FROM senate_activities
WHERE regexp_matches(description, '(?i)\b(farm bill|agriculture improvement act)\b')
UNION ALL
SELECT 'house: specific_issues names it', count(DISTINCT filing_id)
FROM house_filings
WHERE regexp_matches(specific_issues, '(?i)\b(farm bill|agriculture improvement act)\b')
UNION ALL
SELECT 'press: names it', count(*)
FROM press_releases
WHERE regexp_matches(text, '(?i)\b(farm bill|agriculture improvement act)\b');
