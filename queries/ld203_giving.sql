-- LD-203 giving map — the citeable aggregate form of skills/lead-scanner/scripts/lda_ld203_giving.py.
-- The script is the ergonomic front door (resolves an entity/roster to LD-203 filer names,
-- de-dupes amendments, ranks recipients, prints sample keys); these labeled blocks are what an
-- aggregate claim cites, per CLAUDE.md's "aggregate claims cite the exact SQL block + the
-- one-command rebuild + >=3 sampled records" rule.
--
-- Run:  .venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb G1 queries/ld203_giving.sql
--
-- HOW THE JOIN WORKS. LD-203 reports are filed by REGISTRANTS (senate_contributions.registrant_name)
-- and by their individual lobbyists. The script resolves an entity to its concrete filer-name set
-- via lda-entity-resolver (norm_key); these blocks take that RESOLVED NAME SET as an explicit
-- IN(...) list so the SQL is fully deterministic and an evaluator sees exactly which filer names
-- are summed. Demo entity = Coinbase. To cite a different entity, swap the name list (get it from
-- `lda_ld203_giving.py <entity> --json` -> "ld203_filer_names").
--
-- Discipline baked in:
--  * De-dup LD-203 amendments on the contribution IDENTITY (registrant+lobbyist+year+type+amount+
--    payee+honoree+date+contributor) — the loader does not carry LD-203 filing_type, so absent
--    this DISTINCT an amended report double-counts its items. Heuristic; treat totals as a ranking
--    signal and verify specific items via show_record.py (senate_contributions filing_uuid).
--  * Attribution boundary: this is the giving of the registrant itself (in-house filer / trade
--    group / firm) — NOT attributable to an outside firm's individual clients.
--  * Scope: LD-203 only (FECA + honorary + inaugural + library). NOT FEC / Super-PAC money.

-- ==== G1a: total disclosed giving + breakdown by contribution type (Coinbase, de-duped) ====
WITH dd AS (
  SELECT DISTINCT c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
         i.contribution_type, i.amount, i.payee, i.honoree, i.date, i.contributor_name
  FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
  WHERE c.registrant_name IN ('COINBASE, INC.'))
SELECT coalesce(contribution_type, 'ALL') AS contribution_type,
       count(*) AS items, sum(amount)::BIGINT AS total
FROM dd GROUP BY ROLLUP (contribution_type) ORDER BY total DESC NULLS LAST;

-- ==== G1b: top recipients — who the money goes to (honoree, else payee) ====
WITH dd AS (
  SELECT DISTINCT c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
         i.contribution_type, i.amount, i.payee, i.honoree, i.date, i.contributor_name,
         rtrim(upper(trim(coalesce(nullif(i.honoree,''), i.payee, ''))), ' ,.') AS recipient
  FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
  WHERE c.registrant_name IN ('COINBASE, INC.'))
SELECT recipient, count(*) AS items, sum(amount)::BIGINT AS total
FROM dd WHERE recipient <> '' GROUP BY 1 ORDER BY total DESC NULLS LAST LIMIT 15;

-- ==== G1c: filer-role split (org PAC/own giving vs registered lobbyists' personal) + by year ====
WITH dd AS (
  SELECT DISTINCT c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
         i.contribution_type, i.amount, i.payee, i.honoree, i.date, i.contributor_name
  FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
  WHERE c.registrant_name IN ('COINBASE, INC.'))
SELECT filer_type, filing_year, count(*) AS items, sum(amount)::BIGINT AS total
FROM dd GROUP BY GROUPING SETS ((filer_type), (filing_year))
ORDER BY filer_type NULLS FIRST, filing_year;

-- ==== G1d: industry roll-up — aggregate + per-entity giving for a resolved crypto roster ====
-- Swap this IN(...) list for the filer-name set of whatever industry you're mapping. These are
-- the LD-203 filer names the resolver returns for a sample crypto roster (Payward/Kraken's three
-- spellings included — see the lda_ld203_giving.py --loose note on resolver name splits).
WITH dd AS (
  SELECT DISTINCT c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
         i.contribution_type, i.amount, i.payee, i.honoree, i.date, i.contributor_name
  FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
  WHERE c.registrant_name IN (
    'COINBASE, INC.', 'RIPPLE', 'BLOCKCHAIN ASSOCIATION', 'CRYPTO COUNCIL FOR INNOVATION',
    'PARADIGM OPERATIONS LP', 'THE DIGITAL CHAMBER (FORMERLY KNOWN AS CHAMBER OF DIGITAL COMMERCE)',
    'FORIS DAX, INC. & ITS AFFILIATED ENTITIES D/B/A CRYPTO.COM', 'STELLAR DEVELOPMENT FOUNDATION',
    'PAYWARD', 'PAYWARD INC. (FORMERLY KNOWN AS PAYWARD INTERACTIVE, INC. D/B/A KRAKEN)',
    'PAYWARD INTERACTIVE, INC. D/B/A KRAKEN'))
SELECT coalesce(registrant_name, '== INDUSTRY TOTAL ==') AS registrant_name,
       count(*) AS items, sum(amount)::BIGINT AS total
FROM dd GROUP BY ROLLUP (registrant_name) ORDER BY total DESC NULLS LAST;
