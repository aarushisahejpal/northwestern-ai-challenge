# Trace Index

Maps each finding to the skill invocations, trace files, and human decisions behind it.
Naming: `traces/YYYY-MM-DD_<skill-or-phase>_<lead-id>.jsonl`; HTML renderings in `traces/rendered/`.

**Note (2026-07-06):** `DECISIONS.md` was reset for a full-corpus QA pass (see CLAUDE.md); the
rows referenced below now live in `archive/DECISIONS_pilot-triage_2026-07-06.md`, not the active
`DECISIONS.md`.

| finding | skill invocation(s) | trace file(s) | DECISIONS.md entries |
|---|---|---|---|
| (setup, no finding) | lda-corpus-loader build + smoke test | 2026-07-04_phase0-setup.jsonl | archive: 2026-07-04 rows 1–5 |
| L004 kill + L010/L003 leads (pre-finding) | lead-scanner queries (l004/l010/l003 SQL) + show_record deep reads + ledger updates | 2026-07-05_deep-dive_L004-L003.jsonl | archive: 2026-07-05 triage row |
| Full-corpus sweep → L001–L003 (fresh ledger, pre-finding) | smoke_test + lead-scanner full sweep (run_sweep.py, all blocks) + show_record verify (LOC NATION) + ledger/lint | 2026-07-06_full-corpus-sweep_L001-L003.jsonl | (archived: sweep-rediscovery attempt) |
| Generation pass → L020–L025 (fresh ledger, pre-finding) | smoke_test + self-designed lenses (queries/emergence_and_flows.sql E1/E2/E3/E4/F1 via run_sweep.py); NO sweep_2026.sql replay + ledger/lint | 2026-07-06_generation_emergence-flows.jsonl | active DECISIONS.md, all 5 rows |
