---
name: lda-entity-resolver
description: Build a cross-dataset entity table resolving lobbying registrants and clients across Senate LDA JSON and House LDA XML (which has no UUIDs and no standardized casing), using shared senateID/houseID plus normalized-name fuzzy matching. Use when linking the same organization across filings, joining lobbying data to press-release entity mentions, or auditing crosswalk quality.
---

# LDA Entity Resolver

> STATUS: skeleton — validate against the Agent Skills spec and flesh out during Phase 1.

Requires: `db/lda.duckdb` built by `lda-corpus-loader`.

## Usage

```bash
python scripts/resolve_entities.py            # builds entities + entity_aliases tables
python scripts/resolve_entities.py --report   # crosswalk QA report (match-rate, ambiguous clusters)
```

## Guarantees

- Normalization (casing, punctuation, Inc/LLC-style suffixes) is deterministic and documented.
- Senate↔House matches via shared IDs are labeled higher-confidence than fuzzy-name-only matches.
- Ambiguous clusters are reported, not silently merged.
