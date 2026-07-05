---
name: lead-scanner
description: Run investigative lenses (say-vs-pay, revolving door, spend anomalies, Senate-House discrepancies, contribution flows, foreign influence, disclosure gaps) as SQL-first scans over the lobbying database, emitting candidate lead rows with record IDs. Use when generating or refreshing the lead pipeline; scanners return record IDs and one-line hypotheses, never quoted record text.
---

# Lead Scanner

> STATUS: skeleton — validate against the Agent Skills spec and flesh out during Phase 2.

Requires: `db/lda.duckdb` (loader); cross-dataset lenses also require the resolver's entity tables.

## Lenses

Each lens = a SQL query set in `queries/` + a scanning prompt that turns anomaly rows into candidate
ledger rows (`id | hypothesis | lens | named actors | evidence record IDs | next action`).

## Budget rules

- Extraction and filtering stay in SQL; the scanning model only ranks and phrases hypotheses.
- Output is record IDs + one-liners — never quoted record text into the orchestrating context.
- Raw records are only accessed via `lda-corpus-loader`'s `show_record.py`.
