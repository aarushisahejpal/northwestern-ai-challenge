---
name: lda-entity-resolver
description: Build a cross-dataset entity table resolving lobbying registrants and clients across Senate LDA JSON and House LDA XML (which has no UUIDs and no standardized casing), using shared senateID/houseID plus normalized-name fuzzy matching. Use when linking the same organization across filings, joining lobbying data to press-release entity mentions, or auditing crosswalk quality.
---

# LDA Entity Resolver

Requires: a DuckDB built by `lda-corpus-loader`.

## Usage

```bash
python scripts/resolve_entities.py --db db/lda_pilot.duckdb            # builds tables
python scripts/resolve_entities.py --db db/lda_pilot.duckdb --report   # QA report only
```

Builds three tables inside the DB:

| table | grain | notes |
|---|---|---|
| `entities` | one row per resolved entity (kind = registrant / client / foreign_entity) | grouped by deterministic normalized-name key; `canonical_name` = most frequent raw variant |
| `entity_aliases` | one row per raw name variant per dataset | keeps `norm_key`, per-variant senate id, and a sample raw-record pointer — every grouping decision is auditable in SQL |
| `registrant_crosswalk` | one row per senate registrant+client engagement | matched to House filings via the compound key (below); `confidence='id'` on match, NULL otherwise |

## The Senate↔House join key (verified against real records 2026-07-06)

House XML `<senateID>` is the compound string `"<senate_registrant_id>-<senate_client_id>"`
— an engagement-level key, not an org-level one. Join on both parts. Do NOT join
senate `house_registrant_id` to house `<houseID>`: the formats don't overlap (5-digit
vs 9-digit; zero matches in the pilot corpus).

`<houseID>` is a persistent House-Clerk identifier for the registrant-client
relationship (verified 2026-07-06 as what the House disclosure portal's own search
returns) — it is NOT a `filing_id`/filename, and can numerically collide with an
unrelated document: one filing's `<houseID>` matched a real filing_id in this corpus
belonging to a completely different registrant/client pair. Never treat a `<houseID>`
value as a citation key.

## Data facts that bite

- **Senate `client_id` is registrant-scoped, not global.** Comcast alone carries 10+
  distinct client ids (one per registrant relationship). Grouping clients by id
  fragments them; group by normalized name instead. Registrant ids ARE global.
- House organizations have no UUIDs and no standardized casing; they attach to senate
  entities only through the compound-key crosswalk and are never fuzzy-merged.
- Pilot-scale match rate: 52.1% of senate engagements match ≥1 house filing —
  the shortfall is mostly the known-partial House 2026 dump plus senate-only
  engagement types, not resolver misses.

## Guarantees

- Normalization (casing, punctuation, parentheticals, Inc/LLC-style suffixes) is
  deterministic and documented in `norm_name()`.
- Senate↔House matches via shared IDs are labeled (`confidence='id'`); there is no
  silent fuzzy tier.
- Ambiguous clusters (same normalized key, multiple senate ids) are reported by
  `--report`, not silently merged.
