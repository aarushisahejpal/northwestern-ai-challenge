# Trace Index

Maps each finding to the skill invocations, trace files, and human decisions behind it.
Naming: `traces/YYYY-MM-DD_<skill-or-phase>_<lead-id>.jsonl`; HTML renderings in `traces/rendered/`.

| finding | skill invocation(s) | trace file(s) | DECISIONS.md entries |
|---|---|---|---|
| (setup, no finding) | lda-corpus-loader build + smoke test | 2026-07-04_phase0-setup.jsonl | 2026-07-04 rows 1–5 |
| L004 kill + L010/L003 leads (pre-finding) | lead-scanner queries (l004/l010/l003 SQL) + show_record deep reads + ledger updates | 2026-07-05_deep-dive_L004-L003.jsonl | 2026-07-05 triage row |
