---
name: lda-corpus-loader
description: Parse the challenge corpus (congressional press releases JSONL, Senate LDA JSON, House LDA XML) into a single queryable DuckDB database where every row carries a pointer to its raw source record. Use when setting up or rebuilding the investigation database, verifying corpus completeness against the data manual, or fetching a raw record from a citation key.
---

# LDA Corpus Loader

> STATUS: working — validated 2026-07-04 against real corpus records (2026 slice: 3K records
> per dataset, 0 XML parse errors, all three citation-key round-trips pass, smoke test green).
> Full-corpus run and manual-count reconciliation still pending (download incomplete).

Builds `db/lda.duckdb` from the raw corpus at `--data-root` (layout per the challenge data manual).

## Usage

```bash
python scripts/build_db.py --data-root <path>                # full build
python scripts/build_db.py --data-root <path> --years 2025   # pilot / partial build
python scripts/build_db.py --data-root <path> --sample 2025-Q1  # smoke mode (minutes)
python scripts/show_record.py <citation-key>                 # print any raw record
```

Citation keys: Senate `filing_uuid`, House XML filename (filing ID), press release `src_file:src_line`.

## Guarantees

- Every table row carries a raw-record pointer (source file + line/index or filename).
- A sanity report reconciles row counts against the data manual's published scale before the DB is trusted.
- `show_record.py` is the only sanctioned path from a citation to a raw record — agents and evaluators alike.
