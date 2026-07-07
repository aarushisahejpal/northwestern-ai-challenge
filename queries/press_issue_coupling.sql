-- Temporal lobbying-messaging coupling: does congressional PRESS attention on an
-- ALI issue code track lobbying SPEND on that same code, quarter by quarter?
--   Press side  = v_press_issue_quarter (press_issue_mentions tagged by
--                 ISSUE_KEYWORDS in build_db.py; see SHAKY_MAPPINGS there).
--   Spend side  = v_spend_by_issue_quarter (filing income attributed to each
--                 activity code; ranking/trend only, NOT exact dollars, and the
--                 view does NOT dedup amendments -- read the SHAPE, not the level).
-- Run:
--   .venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb P press_issue_coupling.sql
--
-- CONFOUND (why this file correlates SHARES, not raw counts): the press corpus
-- roughly QUADRUPLES over 2022->2025 (~5.3k -> ~24k releases/quarter) and lobbying
-- dollars drift up too, so ANY code with steady relative attention shows a high
-- raw-count correlation that is pure corpus growth. The defensible metric is each
-- code's SHARE of that quarter's total (press_share = code releases / all tagged
-- releases that quarter; spend_share = code income / all attributed income that
-- quarter). Shares cancel the common trend and isolate real co-movement of
-- ATTENTION share vs MONEY share. Corpus spans 2022-Q1..2026-Q1 (2026 = Q1 only),
-- ~17 quarters -- correlations are EXPLORATORY, not inferential, at that n.
-- Authored 2026-07-06 (feature/press-issue-frequency); leads L026 (MMM), L027 (TRD).

-- ==== P0: press vocabulary sanity — raw release volume per issue code ====
-- Which codes the keyword vocabulary fires on corpus-wide (a code with almost no
-- volume can't be coupled; a suspiciously huge one may be a too-broad keyword).
-- n_releases counts DISTINCT releases (the trustworthy volume metric).
SELECT issue_code,
       count(DISTINCT pr_id) AS n_releases,
       count(*)              AS keyword_hits,
       round(count(*) * 1.0 / count(DISTINCT pr_id), 2) AS hits_per_release
FROM press_issue_mentions
GROUP BY issue_code
ORDER BY n_releases DESC;

-- ==== P1: single-issue quarterly series (raw + SHARES) — EYEBALL lead/lag ====
-- The coupled series for ONE code, both raw and share. Edit the code in the WHERE.
-- Read press_share_pct vs spend_share_pct down the quarters: do they move together
-- (coupled), opposite (divergent), or does one turn before the other (lead/lag)?
WITH qmap AS (
  SELECT * FROM (VALUES ('first_quarter',1),('second_quarter',2),
                        ('third_quarter',3),('fourth_quarter',4)) t(filing_period, qn)),
press AS (SELECT issue_code code, filing_year yr, qn, n_releases
          FROM v_press_issue_quarter v JOIN qmap USING (filing_period)),
spend AS (SELECT general_issue_code code, filing_year yr, qn, attributed_income inc
          FROM v_spend_by_issue_quarter v JOIN qmap USING (filing_period)),
ptot AS (SELECT yr, qn, sum(n_releases) t FROM press GROUP BY 1,2),
stot AS (SELECT yr, qn, sum(inc)        t FROM spend GROUP BY 1,2)
SELECT p.yr AS year, p.qn AS q, p.n_releases AS releases,
       round(p.n_releases * 100.0 / pt.t, 2) AS press_share_pct,
       s.inc::BIGINT AS attributed_income,
       round(s.inc * 100.0 / st.t, 2)        AS spend_share_pct
FROM press p JOIN spend s USING (code, yr, qn)
JOIN ptot pt ON pt.yr = p.yr AND pt.qn = p.qn
JOIN stot st ON st.yr = p.yr AND st.qn = p.qn
WHERE p.code = 'MMM'                          -- <-- edit issue code here
ORDER BY year, q;

-- ==== P2: cross-issue coupling ranking on SHARES (concurrent / press-leads / spend-leads) ====
-- One row per code: Pearson r between the two quarterly SHARE series at three shifts.
-- r_concurrent = press_share(t) vs spend_share(t); r_press_leads = press(t) vs
-- spend(t+1) (attention moves first); r_spend_leads = press(t) vs spend(t-1) (money
-- moves first). Dense code x quarter spine (zero-filled) keeps the shift quarter-
-- accurate. Strong POSITIVE r = genuine coupling; strong NEGATIVE r = attention and
-- money move OPPOSITE (a say-vs-pay divergence -- the notable ABSENCE of coupling).
WITH qmap AS (
  SELECT * FROM (VALUES ('first_quarter',1),('second_quarter',2),
                        ('third_quarter',3),('fourth_quarter',4)) t(filing_period, qn)),
press AS (SELECT issue_code code, filing_year*4 + qn AS yq, n_releases
          FROM v_press_issue_quarter v JOIN qmap USING (filing_period)),
spend AS (SELECT general_issue_code code, filing_year*4 + qn AS yq, attributed_income inc
          FROM v_spend_by_issue_quarter v JOIN qmap USING (filing_period)),
ptot AS (SELECT yq, sum(n_releases) t FROM press GROUP BY 1),
stot AS (SELECT yq, sum(inc)        t FROM spend GROUP BY 1),
codes    AS (SELECT code FROM press UNION SELECT code FROM spend),
quarters AS (SELECT yq   FROM press UNION SELECT yq   FROM spend),
grid AS (
  SELECT c.code, q.yq,
         coalesce(p.n_releases, 0) AS releases,
         coalesce(p.n_releases, 0) * 1.0 / pt.t AS pshare,
         coalesce(s.inc, 0)        * 1.0 / st.t AS sshare
  FROM codes c CROSS JOIN quarters q
  LEFT JOIN press p  ON p.code = c.code AND p.yq = q.yq
  LEFT JOIN spend s  ON s.code = c.code AND s.yq = q.yq
  JOIN ptot pt ON pt.yq = q.yq
  JOIN stot st ON st.yq = q.yq),
shifted AS (
  SELECT code, yq, releases, pshare, sshare,
         lead(sshare) OVER (PARTITION BY code ORDER BY yq) AS sshare_next,
         lag(sshare)  OVER (PARTITION BY code ORDER BY yq) AS sshare_prev
  FROM grid),
r AS (
  SELECT code, sum(releases) AS total_releases,
         round(corr(pshare, sshare), 2)      AS r_concurrent,
         round(corr(pshare, sshare_next), 2) AS r_press_leads,
         round(corr(pshare, sshare_prev), 2) AS r_spend_leads
  FROM shifted GROUP BY code)
SELECT code, total_releases, r_concurrent, r_press_leads, r_spend_leads,
       CASE greatest(coalesce(abs(r_concurrent),0), coalesce(abs(r_press_leads),0),
                     coalesce(abs(r_spend_leads),0))
         WHEN abs(r_press_leads) THEN 'press leads spend (t->t+1)'
         WHEN abs(r_spend_leads) THEN 'spend leads press (t-1->t)'
         ELSE 'concurrent' END AS strongest_shift
FROM r
WHERE total_releases >= 1500      -- codes with enough press signal to bother
ORDER BY r_concurrent DESC;

-- ==== P3: divergence — top press-attention quarters that are NOT top spend quarters ====
-- The interesting ABSENCE of coupling, on SHARES (percentile within each code, so it
-- is trend-robust): quarters where a code's press SHARE is in its own top quartile
-- but its spend SHARE is in its bottom half (members loud, paid lobbying share quiet),
-- and the mirror. Candidate say-without-pay / pay-without-say leads.
WITH qmap AS (
  SELECT * FROM (VALUES ('first_quarter',1),('second_quarter',2),
                        ('third_quarter',3),('fourth_quarter',4)) t(filing_period, qn)),
press AS (SELECT issue_code code, filing_year yr, qn, n_releases
          FROM v_press_issue_quarter v JOIN qmap USING (filing_period)),
spend AS (SELECT general_issue_code code, filing_year yr, qn, attributed_income inc
          FROM v_spend_by_issue_quarter v JOIN qmap USING (filing_period)),
ptot AS (SELECT yr, qn, sum(n_releases) t FROM press GROUP BY 1,2),
stot AS (SELECT yr, qn, sum(inc)        t FROM spend GROUP BY 1,2),
j AS (
  SELECT p.code, p.yr, p.qn,
         p.n_releases releases,
         p.n_releases * 1.0 / pt.t AS pshare,
         s.inc * 1.0 / st.t        AS sshare,
         sum(p.n_releases) OVER (PARTITION BY p.code) AS code_releases
  FROM press p JOIN spend s USING (code, yr, qn)
  JOIN ptot pt ON pt.yr = p.yr AND pt.qn = p.qn
  JOIN stot st ON st.yr = p.yr AND st.qn = p.qn),
ranked AS (
  SELECT code, yr, qn, releases, pshare, sshare, code_releases,
         percent_rank() OVER (PARTITION BY code ORDER BY pshare) AS press_pctl,
         percent_rank() OVER (PARTITION BY code ORDER BY sshare) AS spend_pctl
  FROM j)
SELECT code, yr, qn, releases,
       round(pshare*100,2) press_share_pct, round(sshare*100,2) spend_share_pct,
       round(press_pctl,2) press_pctl, round(spend_pctl,2) spend_pctl,
       CASE WHEN press_pctl >= 0.75 AND spend_pctl <= 0.50 THEN 'loud press / quiet spend share'
            ELSE 'quiet press / loud spend share' END AS divergence
FROM ranked
WHERE code_releases >= 3000
  AND ((press_pctl >= 0.75 AND spend_pctl <= 0.50)
    OR (press_pctl <= 0.25 AND spend_pctl >= 0.75))
ORDER BY abs(press_pctl - spend_pctl) DESC, code, yr, qn
LIMIT 30;

-- ==== P4: NAME the actors behind one (code, quarter) — press side ====
-- A coupling/divergence row is aggregate; the named-actor rule needs specific people,
-- filings, dates. LEFT = loudest members (member + citation key src_file:src_line).
-- Edit code + the date window. Pair with P4b for the paid side.
SELECT p.member_name AS actor, p.party, p.state,
       count(DISTINCT p.pr_id) AS n_releases,
       min(p.src_file || ':' || p.src_line) AS sample_citation
FROM press_issue_mentions m JOIN press_releases p ON p.pr_id = m.pr_id
WHERE m.issue_code = 'MMM'                                     -- <-- edit code
  AND substr(p.date, 1, 7) BETWEEN '2025-04' AND '2025-06'    -- <-- edit quarter window
GROUP BY 1, 2, 3
ORDER BY n_releases DESC
LIMIT 15;

-- ==== P4b: paid side for the same (code, quarter) — top lobbying filings ====
-- RIGHT side of P4: who paid to lobby that code that quarter (registrant -> client,
-- income, filing_uuid citation). Watch for single-filing outliers/misreports before
-- citing (e.g. a lone $20M row) -- prefer named, plausible industry actors.
SELECT f.registrant_name, f.client_name, f.income::BIGINT AS income,
       f.filing_year, f.filing_period, f.filing_uuid AS citation
FROM senate_activities a JOIN senate_filings f USING (filing_uuid)
WHERE a.general_issue_code = 'MMM'                             -- <-- edit code
  AND f.filing_year = 2025 AND f.filing_period = 'second_quarter'   -- <-- edit quarter
  AND f.filing_type NOT IN ('RR','RA')
  AND f.income IS NOT NULL
ORDER BY f.income DESC
LIMIT 25;
