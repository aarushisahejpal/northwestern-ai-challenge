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
python scripts/backfill_press_issues.py --db <db>            # (re)tag press_issue_mentions in place
python scripts/add_lobbying_freetext.py --db <db>            # build lobbying_freetext + FTS in place
```

Citation keys: Senate `filing_uuid`, House XML filename (filing ID), press release `src_file:src_line`.

## Guarantees

- Every table row carries a raw-record pointer (source file + line/index or filename).
- A sanity report reconciles row counts against the data manual's published scale before the DB is trusted.
- `show_record.py` is the only sanctioned path from a citation to a raw record — agents and evaluators alike.

## Lobbying free-text search layer (`lobbying_freetext` + FTS)

The lobbying free-text — Senate activity descriptions + House `specific_issues` — is where a
filer describes what it actually lobbies on, and where an industry hidden under many issue codes
and vague categories ("lobbying related to taxation") has to be found by **vocabulary**, not by
issue-code filtering. `build_db.py`'s index step materializes the loader-owned, vocabulary-free
search layer for it (also rebuildable in place with `add_lobbying_freetext.py`, no full rebuild):

- **`lobbying_freetext`** — one row per activity/ali, unioning both chambers into a single doc
  surface. Carries `doc_id` (a build-local surrogate; FTS needs one unique id column) **and** a
  `record_key` (Senate `filing_uuid` / House `filing_id`) + `sub_index`, so every doc still
  resolves to a raw record via `show_record.py`. `issue_code` + `src_file`/`src_index` kept too.
- **FTS/BM25 index** over `lobbying_freetext.txt`, so testing a candidate term is a query, not a
  code edit + rebuild: `fts_main_lobbying_freetext.match_bm25(doc_id, '<query>')`. Built with
  `stemmer='none'`, so it is a **discovery** aid only — the cited *serving* layer stays the
  deterministic keyword tagger `lead-scanner` builds on top (`lobbying_issue_mentions`, from a
  versioned vocabulary). The split keeps findings auditable while vocabulary discovery scales.
