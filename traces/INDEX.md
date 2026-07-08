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
| Press issue-frequency + lobbying–messaging coupling → L026 (MMM say-vs-pay divergence), L027 (TRD tariff coupling, parked) | build_db extend (press_issue_mentions + ISSUE_KEYWORDS tagger + v_press_issue_quarter) + backfill_press_issues.py + smoke_test + press_issue_coupling.sql P0–P4b via run_sweep.py + show_record round-trips + ledger/lint | 2026-07-06_press-issue-coupling_L026-L027.jsonl | active DECISIONS.md, 2026-07-06 rows 6–9 |
| P2 bill cross-check tool (packages lead-scanner; fixes L004 name/number gap) → L028 (SECURE 2.0 quiet-lobby candidate) | lead-scanner packaged: new scripts/bill_lookup.py + bill_aliases.json + queries/p2_bill_crosscheck.sql (P2a–P2d) + SKILL.md rewrite (skeleton removed); smoke_test + acceptance (HR5376 by number & alias, 3 show_record round-trips/dataset) + 12-alias say-vs-pay scan + ledger/lint | 2026-07-07_bill-crosscheck_P2.jsonl | active DECISIONS.md, 2026-07-07 rows (2) |
| P4 industry map (crypto Enterprise-Map "who are the players?" leg; free-text discovery→serving) → L030 (entity-resolved crypto player list, 493/535 name-invisible) | lda-corpus-loader: build_db.py index step adds lobbying_freetext + FTS (+ add_lobbying_freetext.py in-place; sanity-report main-schema fix); lead-scanner: new industry_map.py + industry_lexicon.json + freetext_discovery.py + queries/p4_industry_map.sql (P4a–P4e); serving table lobbying_issue_mentions built (30,922 CRYPTO rows / 9,768 filings); smoke_test extended (lobbying_freetext + FTS) green; acceptance = 3 players round-trip through ld203_giving.py + v_client_canonical_spend + show_record; SKILL.md/CLAUDE.md updated; ledger/lint | 2026-07-07_industry-map-P4_L030.jsonl | active DECISIONS.md, 2026-07-07 rows (5) |
