-- P3 — Quarterly turnover / termination tracker: the citeable aggregate form behind
-- skills/lead-scanner/scripts/lda_turnover.py. Diff a quarter against the corpus:
-- who TERMINATED representation, who HIRED, which clients SWAPPED firms or moved
-- in-house. Run:
--   .venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb P3 queries/p3_turnover.sql
-- Authored 2026-07-10 (P3 build session).
--
-- Method facts (verified 2026-07-10 on db/lda_full.duckdb; reference/corpus-profile.md §3):
-- * Terminations are DECLARED, not inferred: senate filing_type termination family
--   '^[1-4](T|TY|@|@Y)$' — 1T..4T "Termination", 1TY.. "Termination (No Activity)",
--   1@.. "Termination Amendment(, No Activity)"; 18,292 filings corpus-wide. Never
--   infer termination from absence-between-quarters (late/partial posting fabricates it).
-- * Senate-primary: house `form` carries only LD1/LD2 — no termination signal there.
-- * Detection is EXISTENCE of a T-family filing in the (pair, quarter) group; dollars
--   still dedup on filing_period, latest by posted (profile §3), so an amendment
--   posting after the T cannot hide the termination.
-- * Pair identity = registrant_id × resolved CLIENT ENTITY (entity_aliases raw_name
--   join; fallback upper(trim(client_name))). client_id is registrant-scoped AND
--   re-issued on re-registration — grouping by it fabricates "new" engagements for
--   re-registered clients (verified 2026-07-10: Checkmate/Gunvor 2025-Q4).
-- * Client-level dollar context comes from v_client_canonical_spend (P1), never by
--   summing filings.

-- ==== P3a: quarterly turnover trend — terminations / new engagements per quarter ====
-- The beat baseline: is churn in a quarter unusual? First-quarter (2022 Q1) "new"
-- counts are the corpus edge (every pair is new), so read from 2022 Q3 onward.
WITH pairs AS (
  SELECT f.registrant_id, f.filing_type, f.filing_year, f.filing_period,
         (f.filing_year*4 + CASE f.filing_period WHEN 'first_quarter' THEN 0
            WHEN 'second_quarter' THEN 1 WHEN 'third_quarter' THEN 2
            WHEN 'fourth_quarter' THEN 3 END) AS qidx,
         coalesce(ea.entity_id, 'raw:' || upper(trim(f.client_name))) AS ckey
  FROM senate_filings f
  LEFT JOIN entity_aliases ea ON ea.raw_name = f.client_name
       AND ea.kind='client' AND ea.dataset='senate'),
term AS (
  SELECT qidx, count(DISTINCT (registrant_id, ckey)) n_term
  FROM pairs WHERE regexp_matches(filing_type, '^[1-4](T|TY|@|@Y)$') GROUP BY 1),
new_p AS (
  SELECT first_q AS qidx, count(*) n_new
  FROM (SELECT registrant_id, ckey, min(qidx) first_q FROM pairs GROUP BY 1,2)
  GROUP BY 1)
SELECT (qidx // 4) AS yr, 'Q' || (qidx % 4 + 1) AS qtr,
       coalesce(t.n_term, 0) terminations, coalesce(n.n_new, 0) new_engagements
FROM term t FULL JOIN new_p n USING (qidx)
ORDER BY qidx;

-- ==== P3b: terminations in the target quarter, with engagement history ====
-- Ranked by trailing-4-quarter income so a long, large engagement ending outranks a
-- tiny one. re_engaged > 0 = the pair files again AFTER this quarter (came back);
-- new_this_q = the engagement also STARTED this quarter (one-quarter engagement).
WITH pairs AS (
  SELECT f.*, (f.filing_year*4 + CASE f.filing_period WHEN 'first_quarter' THEN 0
            WHEN 'second_quarter' THEN 1 WHEN 'third_quarter' THEN 2
            WHEN 'fourth_quarter' THEN 3 END) AS qidx,
         coalesce(ea.entity_id, 'raw:' || upper(trim(f.client_name))) AS ckey,
         coalesce(e.canonical_name, f.client_name) AS c_canon
  FROM senate_filings f
  LEFT JOIN entity_aliases ea ON ea.raw_name = f.client_name
       AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id = ea.entity_id),
tq AS (SELECT 2025*4 + (4-1) AS t),        -- <-- edit target quarter (year, Q)
term AS (
  SELECT registrant_id, ckey, min(registrant_name) registrant,
         min(c_canon) client, min(filing_uuid) term_uuid
  FROM pairs WHERE regexp_matches(filing_type, '^[1-4](T|TY|@|@Y)$')
    AND qidx = (SELECT t FROM tq)
  GROUP BY 1,2),
hist AS (   -- deduped activity history per pair (registrations excluded from sums)
  SELECT registrant_id, ckey, min(qidx) first_q, count(*) n_quarters,
         sum(income) FILTER (WHERE qidx > (SELECT t FROM tq)-4
                               AND qidx <= (SELECT t FROM tq)) trail4_income,
         count(*) FILTER (WHERE qidx > (SELECT t FROM tq)) re_engaged
  FROM (SELECT * FROM pairs WHERE filing_type NOT IN ('RR','RA')
        QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey, filing_year,
          filing_period ORDER BY posted DESC, filing_uuid) = 1)
  GROUP BY 1,2)
SELECT t.registrant, t.client, h.trail4_income::BIGINT trail4_income, h.n_quarters,
       (h.first_q // 4) || '-Q' || (h.first_q % 4 + 1) first_seen,
       h.first_q = (SELECT t FROM tq) new_this_q, h.re_engaged, t.term_uuid
FROM term t JOIN hist h USING (registrant_id, ckey)
ORDER BY coalesce(h.trail4_income, 0) DESC, t.client, t.registrant LIMIT 25;

-- ==== P3c: new engagements in the target quarter (first-ever filing, incl. registration) ====
-- Entity-grouped so a re-registration is NOT "new" (the Gunvor trap). Income NULL =
-- registration-only so far (RR filed, first quarterly not yet due/posted).
WITH pairs AS (
  SELECT f.*, (f.filing_year*4 + CASE f.filing_period WHEN 'first_quarter' THEN 0
            WHEN 'second_quarter' THEN 1 WHEN 'third_quarter' THEN 2
            WHEN 'fourth_quarter' THEN 3 END) AS qidx,
         coalesce(ea.entity_id, 'raw:' || upper(trim(f.client_name))) AS ckey,
         coalesce(e.canonical_name, f.client_name) AS c_canon
  FROM senate_filings f
  LEFT JOIN entity_aliases ea ON ea.raw_name = f.client_name
       AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id = ea.entity_id),
tq AS (SELECT 2025*4 + (4-1) AS t),        -- <-- edit target quarter (year, Q)
firstq AS (
  SELECT registrant_id, ckey, min(registrant_name) registrant,
         min(c_canon) client, min(qidx) first_q,
         arg_min(filing_uuid, (qidx, filing_uuid)) first_uuid
  FROM pairs GROUP BY 1,2 HAVING min(qidx) = (SELECT t FROM tq)),
dollars AS (
  SELECT registrant_id, ckey, income, filing_uuid
  FROM pairs WHERE filing_type NOT IN ('RR','RA') AND qidx = (SELECT t FROM tq)
  QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey, filing_year,
    filing_period ORDER BY posted DESC, filing_uuid) = 1)
SELECT f.registrant, f.client, d.income::BIGINT q_income,
       coalesce(d.filing_uuid, f.first_uuid) cite_uuid,
       d.filing_uuid IS NULL AS registration_only
FROM firstq f LEFT JOIN dollars d USING (registrant_id, ckey)
ORDER BY coalesce(d.income, 0) DESC, f.client, f.registrant LIMIT 25;

-- ==== P3d: registrant swaps + in-house moves around the target quarter ====
-- Client entity terminates firm A in the target quarter AND first-files with a
-- different registrant within ±1 quarter. move = 'to-inhouse' when the new
-- registrant resolves to the client itself; 'from-inhouse' when the terminated one
-- does (norm_key equality bridges the resolver's registrant/client split, as in P1).
WITH pairs AS (
  SELECT f.*, (f.filing_year*4 + CASE f.filing_period WHEN 'first_quarter' THEN 0
            WHEN 'second_quarter' THEN 1 WHEN 'third_quarter' THEN 2
            WHEN 'fourth_quarter' THEN 3 END) AS qidx,
         coalesce(ea.entity_id, 'raw:' || upper(trim(f.client_name))) AS ckey,
         coalesce(e.canonical_name, f.client_name) AS c_canon, e.norm_key AS c_norm,
         rn.norm_key AS r_norm
  FROM senate_filings f
  LEFT JOIN entity_aliases ea ON ea.raw_name = f.client_name
       AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id = ea.entity_id
  LEFT JOIN entity_aliases ra ON ra.raw_name = f.registrant_name
       AND ra.kind='registrant' AND ra.dataset='senate'
  LEFT JOIN entities rn ON rn.entity_id = ra.entity_id),
tq AS (SELECT 2025*4 + (4-1) AS t),        -- <-- edit target quarter (year, Q)
term AS (
  SELECT registrant_id, ckey, min(registrant_name) old_firm,
         min(c_canon) client, min(c_norm) c_norm,
         min(r_norm) old_r_norm, min(filing_uuid) term_uuid
  FROM pairs WHERE regexp_matches(filing_type, '^[1-4](T|TY|@|@Y)$')
    AND qidx = (SELECT t FROM tq)
  GROUP BY 1,2),
hires AS (
  SELECT registrant_id, ckey, min(registrant_name) new_firm,
         min(r_norm) new_r_norm, min(qidx) first_q,
         arg_min(filing_uuid, (qidx, filing_uuid)) hire_uuid
  FROM pairs GROUP BY 1,2
  HAVING min(qidx) BETWEEN (SELECT t FROM tq)-1 AND (SELECT t FROM tq)+1)
SELECT te.client, te.old_firm, he.new_firm,
       he.first_q - (SELECT t FROM tq) AS hire_dq,
       CASE WHEN he.new_r_norm IS NOT NULL AND he.new_r_norm = te.c_norm THEN 'to-inhouse'
            WHEN te.old_r_norm IS NOT NULL AND te.old_r_norm = te.c_norm THEN 'from-inhouse'
            ELSE '' END AS move,
       v.canonical_spend::BIGINT client_q_spend,
       te.term_uuid, he.hire_uuid
FROM term te
JOIN hires he ON he.ckey = te.ckey AND he.registrant_id <> te.registrant_id
LEFT JOIN v_client_canonical_spend v ON v.client_norm_key = te.c_norm
     AND v.filing_year*4 + CASE v.filing_period WHEN 'first_quarter' THEN 0
         WHEN 'second_quarter' THEN 1 WHEN 'third_quarter' THEN 2
         WHEN 'fourth_quarter' THEN 3 END = (SELECT t FROM tq)
ORDER BY coalesce(v.canonical_spend, 0) DESC, te.client, te.old_firm, he.new_firm LIMIT 25;

-- ==== P3e: registrant churn scoreboard for the target quarter ====
-- Which FIRMS lost / signed the most engagements. lost_trail4 = trailing-4-quarter
-- income of the engagements that terminated (the book of business walking out).
WITH pairs AS (
  SELECT f.*, (f.filing_year*4 + CASE f.filing_period WHEN 'first_quarter' THEN 0
            WHEN 'second_quarter' THEN 1 WHEN 'third_quarter' THEN 2
            WHEN 'fourth_quarter' THEN 3 END) AS qidx,
         coalesce(ea.entity_id, 'raw:' || upper(trim(f.client_name))) AS ckey
  FROM senate_filings f
  LEFT JOIN entity_aliases ea ON ea.raw_name = f.client_name
       AND ea.kind='client' AND ea.dataset='senate'),
tq AS (SELECT 2025*4 + (4-1) AS t),        -- <-- edit target quarter (year, Q)
dedup AS (
  SELECT * FROM pairs WHERE filing_type NOT IN ('RR','RA')
  QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey, filing_year,
    filing_period ORDER BY posted DESC, filing_uuid) = 1),
term AS (
  SELECT registrant_id, min(registrant_name) registrant, count(DISTINCT ckey) n_lost,
         sum(trail4) lost_trail4
  FROM (SELECT p.registrant_id, p.registrant_name, p.ckey,
          (SELECT sum(d.income) FROM dedup d WHERE d.registrant_id = p.registrant_id
             AND d.ckey = p.ckey AND d.qidx > (SELECT t FROM tq)-4
             AND d.qidx <= (SELECT t FROM tq)) trail4
        FROM pairs p WHERE regexp_matches(p.filing_type, '^[1-4](T|TY|@|@Y)$')
          AND p.qidx = (SELECT t FROM tq)
        GROUP BY 1,2,3, trail4)
  GROUP BY 1),
new_p AS (
  SELECT registrant_id, count(*) n_new
  FROM (SELECT registrant_id, ckey FROM pairs
        GROUP BY 1,2 HAVING min(qidx) = (SELECT t FROM tq))
  GROUP BY 1)
SELECT coalesce(t.registrant,
         (SELECT min(registrant_name) FROM pairs p WHERE p.registrant_id = n.registrant_id)) registrant,
       coalesce(t.n_lost, 0) n_lost, t.lost_trail4::BIGINT lost_trail4,
       coalesce(n.n_new, 0) n_new,
       coalesce(n.n_new, 0) - coalesce(t.n_lost, 0) net
FROM term t FULL JOIN new_p n USING (registrant_id)
ORDER BY coalesce(t.n_lost, 0) + coalesce(n.n_new, 0) DESC, registrant LIMIT 25;
