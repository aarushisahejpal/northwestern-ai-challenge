-- L004 deep dive: bills heavily lobbied but publicly near-silent (say-vs-pay).
-- Bills from sweep#C1b: HR7567, HR4552, S2296; loud comparator HR6938.
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_2026.duckdb L004 queries/l004_quiet_bills.sql
--
-- Supersedes sweep#C1b's dollar totals: C1b summed senate + house datasets, but
-- LD-2 quarterlies are filed with BOTH chambers (H1b showed identical incomes
-- after dedup), so cross-dataset sums double-count the same filing. Blocks here
-- are senate-primary, amendment/duplicate-deduped per the CLAUDE.md rule; L004e
-- checks what the house dataset adds that senate-side misses.
-- Income remains filing-level: a filing naming several bills attributes its full
-- income to each (ranking signal, not exact dollars).

-- ==== L004a: corrected headline — per-bill attributed dollars, senate-primary ====
WITH latest AS (
  SELECT filing_uuid, registrant_name, client_name, income
  FROM senate_filings
  QUALIFY row_number() OVER (PARTITION BY upper(trim(registrant_name)),
    upper(trim(client_name)), filing_year, filing_period ORDER BY posted DESC) = 1),
m AS (
  SELECT DISTINCT bill, record_key FROM bill_mentions
  WHERE dataset = 'senate' AND bill IN ('HR7567', 'HR4552', 'S2296', 'HR6938')),
p AS (
  SELECT bill, count(*) AS press_mentions FROM bill_mentions
  WHERE dataset = 'press' GROUP BY 1)
SELECT m.bill, count(*) AS filings, sum(l.income)::BIGINT AS senate_attributed,
       coalesce(p.press_mentions, 0) AS press_mentions
FROM m JOIN latest l ON m.record_key = l.filing_uuid
LEFT JOIN p USING (bill)
GROUP BY m.bill, p.press_mentions
ORDER BY senate_attributed DESC;

-- ==== L004b: top clients behind each quiet bill ====
SELECT bill, client_name, registrant_name, attributed_income, filings FROM (
  SELECT m.bill, l.client_name, l.registrant_name,
         sum(l.income)::BIGINT AS attributed_income, count(*) AS filings,
         row_number() OVER (PARTITION BY m.bill
                            ORDER BY sum(l.income) DESC NULLS LAST) AS rk
  FROM (SELECT DISTINCT bill, record_key FROM bill_mentions
        WHERE dataset = 'senate' AND bill IN ('HR7567', 'HR4552', 'S2296')) m
  JOIN (SELECT filing_uuid, registrant_name, client_name, income
        FROM senate_filings
        QUALIFY row_number() OVER (PARTITION BY upper(trim(registrant_name)),
          upper(trim(client_name)), filing_year, filing_period
          ORDER BY posted DESC) = 1) l
    ON m.record_key = l.filing_uuid
  GROUP BY 1, 2, 3) t
WHERE rk <= 10
ORDER BY bill, attributed_income DESC;

-- ==== L004c: top filings per bill — record keys for the deep read ====
SELECT bill, client_name, registrant_name, income, filing_uuid FROM (
  SELECT m.bill, l.client_name, l.registrant_name, l.income::BIGINT AS income,
         l.filing_uuid,
         row_number() OVER (PARTITION BY m.bill
                            ORDER BY l.income DESC NULLS LAST) AS rk
  FROM (SELECT DISTINCT bill, record_key FROM bill_mentions
        WHERE dataset = 'senate' AND bill IN ('HR7567', 'HR4552', 'S2296')) m
  JOIN (SELECT filing_uuid, registrant_name, client_name, income
        FROM senate_filings
        QUALIFY row_number() OVER (PARTITION BY upper(trim(registrant_name)),
          upper(trim(client_name)), filing_year, filing_period
          ORDER BY posted DESC) = 1) l
    ON m.record_key = l.filing_uuid) t
WHERE rk <= 5
ORDER BY bill, income DESC;

-- ==== L004d: the few press mentions — who said what, when ====
SELECT bm.bill, pr.member_name, pr.party, pr.state, pr.date, pr.title,
       bm.record_key
FROM bill_mentions bm
JOIN press_releases pr
  ON bm.record_key = pr.src_file || ':' || pr.src_line
WHERE bm.dataset = 'press' AND bm.bill IN ('HR7567', 'HR4552', 'S2296')
ORDER BY bm.bill, pr.date;

-- ==== L004f: bill identity from the filers' own activity text ====
-- The corpus names the bills itself (no outside data needed): pull text windows
-- around each bill number from senate activity descriptions.
SELECT * FROM (
  SELECT 'HR7567' AS bill,
         regexp_extract(description, '.{0,100}7567.{0,140}') AS context, filing_uuid,
         row_number() OVER () AS rk
  FROM senate_activities WHERE description LIKE '%7567%'
  UNION ALL
  SELECT 'HR4552', regexp_extract(description, '.{0,100}4552.{0,140}'), filing_uuid,
         row_number() OVER ()
  FROM senate_activities WHERE description LIKE '%4552%'
  UNION ALL
  SELECT 'S2296', regexp_extract(description, '.{0,100}2296.{0,140}'), filing_uuid,
         row_number() OVER ()
  FROM senate_activities WHERE description LIKE '%2296%') t
WHERE rk <= 5 ORDER BY bill, rk;

-- ==== L004g: artifact check — press talks names, filings talk numbers ====
-- If press releases discuss these bills by popular name (never by number), the
-- "lobbied but silent" pattern is a naming artifact of number-based matching.
SELECT 'farm bill (text)' AS phrase, count(*) AS press_releases
FROM press_releases WHERE text ILIKE '%farm bill%'
UNION ALL SELECT 'NDAA / Natl Defense Authorization (text)', count(*)
FROM press_releases WHERE text ILIKE '%NDAA%' OR text ILIKE '%national defense authorization%'
UNION ALL SELECT 'appropriations (text)', count(*)
FROM press_releases WHERE text ILIKE '%appropriations%'
UNION ALL SELECT 'transportation-HUD approps (text)', count(*)
FROM press_releases WHERE text ILIKE '%housing and urban development%'
UNION ALL SELECT 'ductile iron / pipe materials (text)', count(*)
FROM press_releases WHERE text ILIKE '%ductile iron%' OR text ILIKE '%pipe material%'
UNION ALL SELECT 'water infrastructure (text)', count(*)
FROM press_releases WHERE text ILIKE '%water infrastructure%';

-- ==== L004h: DIPRA profile — who lobbies for them, on what, in both chambers ====
SELECT 'senate' AS side, filing_uuid AS record_key, filing_type, filing_period AS period,
       registrant_name, income::BIGINT AS income, posted
FROM senate_filings WHERE upper(client_name) LIKE '%DUCTILE IRON%'
UNION ALL
SELECT 'house', filing_id, form, report_period, organization_name, income::BIGINT, NULL
FROM house_filings WHERE upper(client_name) LIKE '%DUCTILE IRON%'
ORDER BY side, record_key;

-- ==== L004i: DIPRA follow-ups — pipe press releases + registrant house presence ====
SELECT 'press: pipe-materials mention' AS what,
       member_name || ' (' || coalesce(party, '?') || '-' || coalesce(state, '?') || ') ' ||
       coalesce(date, '?') || ' — ' || coalesce(title, '') AS detail,
       src_file || ':' || src_line AS record_key
FROM press_releases
WHERE text ILIKE '%ductile iron%' OR text ILIKE '%pipe material%'
UNION ALL
SELECT 'house filings by Bradley Arant (all clients)',
       'n=' || count(*) || ', distinct clients=' || count(DISTINCT client_name), NULL
FROM house_filings WHERE upper(organization_name) LIKE '%BRADLEY ARANT%'
UNION ALL
SELECT 'senate filings by Bradley Arant (all clients)',
       'n=' || count(*) || ', distinct clients=' || count(DISTINCT client_name), NULL
FROM senate_filings WHERE upper(registrant_name) LIKE '%BRADLEY ARANT%';

-- ==== L004j: house dump snapshot check — does house Q1 predate the Apr 20 deadline? ====
-- Bradley Arant has 0 house filings for ANY client; hypothesis: the house 2026-Q1
-- XML dump was generated before most Q1 reports were filed (due Apr 20).
SELECT 'senate Q1-2026 posted before Apr 15' AS cohort, count(*) AS n
FROM senate_filings
WHERE filing_year = 2026 AND filing_type LIKE 'Q1%' AND substr(posted, 1, 10) < '2026-04-15'
UNION ALL
SELECT 'senate Q1-2026 posted Apr 15 or later', count(*)
FROM senate_filings
WHERE filing_year = 2026 AND filing_type LIKE 'Q1%' AND substr(posted, 1, 10) >= '2026-04-15'
UNION ALL
SELECT 'house Q1-2026 filings total', count(*)
FROM house_filings WHERE report_period = 'Q1';

-- ==== L004k: the other side of the pipe war — PVC/plastics money on pipe issues ====
SELECT DISTINCT f.client_name, f.registrant_name, f.income::BIGINT AS income,
       a.general_issue_code AS code, f.filing_uuid
FROM senate_activities a JOIN senate_filings f USING (filing_uuid)
WHERE (upper(f.client_name) LIKE '%PVC%' OR upper(f.client_name) LIKE '%PLASTIC%'
       OR (a.description ILIKE '%pipe%' AND a.description NOT ILIKE '%pipeline%'))
ORDER BY income DESC NULLS LAST
LIMIT 25;

-- ==== L004e: house-only coverage — org+client pairs missing from senate side ====
WITH sm AS (
  SELECT DISTINCT m.bill, upper(trim(f.registrant_name)) AS org,
         upper(trim(f.client_name)) AS client
  FROM bill_mentions m JOIN senate_filings f ON m.record_key = f.filing_uuid
  WHERE m.dataset = 'senate' AND m.bill IN ('HR7567', 'HR4552', 'S2296')),
hm AS (
  SELECT DISTINCT m.bill, upper(trim(f.organization_name)) AS org,
         upper(trim(f.client_name)) AS client, f.income, f.filing_id
  FROM bill_mentions m JOIN house_filings f ON m.record_key = f.filing_id
  WHERE m.dataset = 'house' AND m.bill IN ('HR7567', 'HR4552', 'S2296'))
SELECT hm.bill, hm.org, hm.client, hm.income::BIGINT AS income, hm.filing_id
FROM hm LEFT JOIN sm USING (bill, org, client)
WHERE sm.org IS NULL
ORDER BY hm.bill, hm.income DESC NULLS LAST
LIMIT 30;
