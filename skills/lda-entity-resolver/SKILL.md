---
name: lda-entity-resolver
description: Build a cross-dataset entity table resolving lobbying registrants and clients across Senate LDA JSON and House LDA XML (which has no UUIDs and no standardized casing), using shared senateID/houseID plus normalized-name fuzzy matching. Use when linking the same organization across filings, joining lobbying data to press-release entity mentions, or auditing crosswalk quality.
---

# LDA Entity Resolver

Requires: a DuckDB built by `lda-corpus-loader`. Corpus bindings (join keys, citation keys, and the
facts this tool relies on) live in `reference/corpus-profile.md` (§2, §4) — the single source of truth.

## Usage

```bash
python scripts/resolve_entities.py --db db/lda_pilot.duckdb            # builds tables
python scripts/resolve_entities.py --db db/lda_pilot.duckdb --report   # QA report only
```

Builds three tables and one view inside the DB:

| table | grain | notes |
|---|---|---|
| `entities` | one row per resolved entity (kind = registrant / client / foreign_entity) | grouped by deterministic normalized-name key; `canonical_name` = most frequent raw variant |
| `entity_aliases` | one row per raw name variant per dataset | keeps `norm_key`, per-variant senate id, and a sample raw-record pointer — every grouping decision is auditable in SQL |
| `registrant_crosswalk` | one row per senate registrant+client engagement | matched to House filings via the compound key (below); `confidence='id'` on match, NULL otherwise |
| `v_client_canonical_spend` (view) | one row per (client, year, quarter) | senate lobbying spend with the in-house rollup double-count removed (P1) — see below |

## Canonical client spend (P1) — the rollup double-count

A client that lobbies in-house files as its **own** registrant (registrant name ==
client name) and reports its **total** spend; outside firms it hires also file,
reporting income already inside that total. Summing every filing for a client therefore
overstates it (corpus-wide ≈12% for 2025). `v_client_canonical_spend` fixes this: per
(client, quarter), `canonical_spend = greatest(inhouse_amount, outside_amount)` — never
their sum — with `has_inhouse_filing`, both components, `naive_sum_all`, `double_count_delta`,
and a `method` label all exposed so any figure is auditable. `amount` uses the row's
reported figure regardless of the income/expenses field (some in-house filers report
under `income`). Amendments deduped on `filing_period` (latest `posted`), same as
`sweep_2026.sql#H1c`; senate-only. **Always aggregate client spend from this view, never
by summing `senate_filings` directly.** Cited demos + lead QA: `queries/p1_canonical_spend.sql`.
Prior art / independent cross-check: the team's lobbyR `flag_client_registrant_conflict()`
and `flag_dupes()` (disclose in README §4).

## Corpus facts this resolver relies on

The join keys and id-namespace traps are the corpus's, not this tool's — full detail with
verification dates in `reference/corpus-profile.md` (§2 citation keys, §4 entity resolution). The
load-bearing ones here:

- **Join Senate↔House on the compound `<senateID>` = `"<senate_registrant_id>-<senate_client_id>"`**
  (engagement-level, verified 2026-07-06), never senate `house_registrant_id` → house `<houseID>`
  (formats don't overlap). `<houseID>` is a House-Clerk relationship id, **not** a citation key.
- **`client_id` is registrant-scoped** (Comcast 10+) — group clients by normalized name/entity,
  never by `client_id`; registrant ids ARE global.
- House orgs have no UUIDs or standardized casing — they attach only through the compound-key
  crosswalk, never fuzzy-merged (see Guarantees).

Match-rate QA (how much of senate reconciles to house) is emitted by `--report`; the shortfall is
mostly the known-partial House dump + senate-only engagement types, not resolver misses.

## Guarantees

- Normalization (casing, punctuation, parentheticals, Inc/LLC-style suffixes) is
  deterministic and documented in `norm_name()`.
- Senate↔House matches via shared IDs are labeled (`confidence='id'`); there is no
  silent fuzzy tier.
- Ambiguous clusters (same normalized key, multiple senate ids) are reported by
  `--report`, not silently merged.
