# Investigation Ledger

Single source of truth for what has been checked, what is open, which entities matter, and which
threads went cold. **Write protocol:** sub-agents never edit this file — they return candidate rows;
only the orchestrating session (or a human) commits them. Read at session start; write at any status
change and at session end.

**Status state machine:** `open → triaged → investigating → verified | dead`. Any lead may move to
`parked` (cold) with a reason and a revisit trigger. **Cold ≠ dead:** dead = refuted or judged not
newsworthy (reason recorded); cold = promising but blocked/deprioritized, reconsidered at every
triage checkpoint. New leads arriving mid-stream enter as `open` and are considered at the next
triage checkpoint.

**Named-actor rule:** a lead with no specific actor, date, and record ID cannot pass triage.

**Fresh start (2026-07-06):** this ledger was reset to empty for a QA pass on the full corpus
(`db/lda_full.duckdb`, 2022-2026) — a deliberate, one-time reset, not a standing process. Prior
pilot-scale investigation (leads L001-L011, entities checked, queries run) is archived at
`archive/LEDGER_pilot-triage_2026-07-06.md` for reference; nothing there should be assumed true or
false here without independent re-derivation against the full corpus.

## Leads

| id | hypothesis (one line) | lens | named actors | status | owner | evidence so far (record IDs) | next action | updated |
|---|---|---|---|---|---|---|---|---|
| L001 | "STATE OF LOC NATION GLOBAL PUBLIC BENEFIT CORPORATION" self-reports exactly $20M/quarter ($80M in 2025) — the corpus's single largest reported income — a self-declared-nation / vanity filing, not real lobbying spend | S1a (top spenders) + dedup drill | Registrant LOC COMMUNITY ASSOCIATION (senate reg 401108853); posted_by / lobbyist REV DR CHRISTINA CLEMENT (covered-position text "Head of State", "2024 Presidential Candidate Assumed the Presidency"); client STATE OF LOC NATION GPBC; issue focus HR40 (reparations) | investigating | opus-4.8 (this session) | abaac383-…-4d59eea (2025 Q3, $20M, raw-read confirmed); c2d195d2-…-cacb (2025 Q2); f77a4908-…-ee6946 (2025 Q4); d60611b7-…-0874e67 (2025 4A); RR 5000632b-…-6a40c91 (2024-09 registration) | Verify per finding-verifier; decide integrity-writeup vs exclude-and-note; flag exclusion from all $-ranked lenses (also inflates C1b HR40 total) | 2026-07-06 |
| L002 | GlobalFoundries' U.S. semiconductor/CHIPS lobbying traces to ~82% Abu Dhabi state ownership (Mubadala 61% + MTI 21%), disclosed in its own LD-2 foreign-entity fields | S3 (foreign influence) | Client GLOBALFOUNDRIES U.S. INC.; foreign owners MUBADALA TECHNOLOGY INVESTMENT COMPANY (AE), MTI INVESTMENT COMPANY LLC (AE); registrants RIDGE PATH STRATEGIES, COZEN O'CONNOR PUBLIC STRATEGIES, J.A. GREEN AND COMPANY | triaged | opus-4.8 (this session) | f60e8ced-…-712a032 (2024); 7d21a3b7-…-c07279f7 (2024); ae96bcb0-…-ebb4ea68 (2025); 7b017b92-…-53bd025b (2026) | Outside-context novelty scan anchored to disclosure dates (ownership is publicly known); note modest dollars ($290K–745K/yr) — likely context, not scoop | 2026-07-06 |
| L003 | Regulated corporations report multimillion-dollar LD-203 "honorary"/inaugural/library payments alongside active lobbying — a disclosed "pay" channel distinct from PAC giving | S4 (contribution flows) + items ≥ $1M drill | JBS USA FOOD COMPANY HOLDINGS ($5M "Donald Trump and J.D. Vance", 2025); HEALTH CARE SERVICE CORP/HCSC ($5M "President Barak Obama", 2025); APPLE INC. ($3M Obama Foundation / My Brother's Keeper, 2023); VANTIVE US HEALTHCARE ($2.5M "White House Ballroom Project", 2025); STATE FARM ($2.65M "Rep. Virginia Foxx", 2025) | triaged | opus-4.8 (this session) | ef66ecc1-…-7709cf2698 (JBS $5M); 418db336-…-daf821f5f (HCSC $5M); 06bcff41-…-b55a084a84 (Apple $3M); c205e636-…-6ec938b826 (Vantive $2.5M); 91514e3d-…-9bd47e4e0 (State Farm $2.65M) | Separate already-public (JBS inaugural) from under-reported (Vantive/ballroom, State Farm/Foxx); verify amounts vs raw records; cross-check each filer's concurrent lobbying issues | 2026-07-06 |

## Entities checked

| entity (entity_id) | verdict | records examined | date |
|---|---|---|---|
| LOC COMMUNITY ASSOCIATION / STATE OF LOC NATION GPBC (senate reg 401108853) | Anomalous — fabricated $20M/qtr self-filed income; sovereign/vanity filing, exclude from $ rankings (→ L001) | 15 senate filings (9 with $20M); abaac383 raw-read | 2026-07-06 |
| GLOBALFOUNDRIES U.S. INC. (client) | Foreign-owned (Mubadala/MTI, Abu Dhabi ~82%), fully disclosed in LD-2; modest lobbying spend (→ L002) | 63 filings 2022–2026; S3 foreign-entity rows | 2026-07-06 |

## Queries run

| date | SQL (file in queries/) | one-line result |
|---|---|---|
| 2026-07-06 | sweep_2026.sql — full sweep, all blocks (`run_sweep.py db/lda_full.duckdb`) | S1a top client = LOC NATION $180M (bogus, → L001); S1b/S1c nominal; S3 → GlobalFoundries Emirati ownership (→ L002); S4 → large corporate honorary/inaugural $ (→ L003) |
| 2026-07-06 | sweep_2026.sql#H1c / #H1d (fixed ID-join reconciliation) | Only tiny deltas (max $90K) and 0 chronic mis-reporters — confirms the documented amendment-symmetry artifact; no lead |
| 2026-07-06 | sweep_2026.sql#S1d (resolved-entity spenders) + entity_aliases fanout check | S1d UNRELIABLE: `entity_aliases` has ~52 duplicate (client/senate) rows per entity (Comcast) → dollar totals inflated ~52x ($1.0B vs real $19M). Use S1a for spender rankings |
| 2026-07-06 | sweep_2026.sql#C1b (say-vs-pay by $) | HR40 shows $320M on only 113 filings/7 press — attribution artifact (income double-counted across multi-bill filings; LOC NATION filings contribute), not a real signal |

## Cold threads

| lead id | parked reason | revisit trigger | date parked |
|---|---|---|---|
| infra: S1d alias fanout | `entity_aliases` has ~52 duplicate client/senate rows per entity → S1d $ totals ~52x inflated; not fixed this session (resolver rebuild out of scope per brief) | before any lens relies on resolved-entity dollar sums | 2026-07-06 |
| data-quality: S5 gaps | Phoenix Global Organization Inc (282/282 filings null income+expenses) and peers show systematic non-disclosure, but no dollar story and no single record/date — fails named-actor rule as a standalone lead | a filer in this set surfaces inside another lead | 2026-07-06 |
