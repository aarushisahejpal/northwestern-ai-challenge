# Decision Log — human-judgment moments

Required by the brief: interaction traces must show "the moments where human judgment intervened."
Every human intervention — triage selections, lead kills, editorial calls, legal-flag decisions,
scope changes — gets a row. Referenced from README §3 and from each finding's verification block.

**Fresh start (2026-07-06):** this log was reset to empty alongside LEDGER.md for a QA pass on the
full corpus (`db/lda_full.duckdb`, 2022-2026) — a deliberate, one-time reset, not a standing process.
Prior decisions (deadline, pilot-corpus scope, repo layout, the L001/L003/L004/L010/L006 triage and
correction history) are archived at `archive/DECISIONS_pilot-triage_2026-07-06.md`.

| date | decision | rationale | who | trace file |
|---|---|---|---|---|
| 2026-07-06 | Resolved raw-record access to `../data/data/` (parent), not the repo's `data/` | The repo's gitignored `data/` held unrelated SEC litigation files, not the LDA corpus; the real corpus (senate/house/congress_press, 2022–2026) is at `Northwestern Project/data/data/`. `show_record.py` needs `--data-root "…/data/data"` on this box. Submission convention (`--data-root data/`) stays correct for evaluators, who place the corpus at `data/`. Surfaced to user; did not touch the SEC files. | opus-4.8 session | traces/2026-07-06_full-corpus-sweep_L001-L003.jsonl |
| 2026-07-06 | Set S1d aside; ranked spenders from S1a instead | `entity_aliases` has ~52 duplicate (client/senate) rows per resolved entity, so the S1d join inflates dollar totals ~52x (Comcast $1.0B vs real $19.3M). Judged a resolver data-quality bug, not an investigative signal; resolver rebuild is out of scope per the session brief. | opus-4.8 session | traces/2026-07-06_full-corpus-sweep_L001-L003.jsonl |
| 2026-07-06 | Triaged L001 (LOC NATION) as a data-integrity anomaly and flagged it for exclusion from all $-ranked lenses | Exactly $20M/quarter, round, self-filed, no expenses, by a registrant whose lobbyist lists covered position "Head of State" / "2024 Presidential Candidate Assumed the Presidency" — not credible lobbying spend. It is S1a's #1 client and a large part of C1b's HR40 $320M artifact, so leaving it in poisons the spender and say-vs-pay rankings. | opus-4.8 session | traces/2026-07-06_full-corpus-sweep_L001-L003.jsonl |
| 2026-07-06 | Did NOT open a cross-chamber reconciliation lead | H1c/H1d (fixed ID-join, amendment-symmetric dedup) show only tiny deltas (≤$90K) and 0 chronic mis-reporters — reproduces and confirms the documented artifact rather than a story; nothing to chase. | opus-4.8 session | traces/2026-07-06_full-corpus-sweep_L001-L003.jsonl |
| 2026-07-06 | Triage picks for the session: L001 (integrity), L002 (foreign ownership), L003 (corporate honorary/inaugural $) | Only leads satisfying the named-actor rule (specific actor + date + record ID) were logged; aggregate-only patterns (S5 income gaps, C1b press=0 bills) were parked or dropped per the discipline that a dataset summary is not a lead. L002/L003 include items likely already public (GF ownership, JBS inaugural) — logged on their own merits per brief, pending an outside-context novelty pass. | opus-4.8 session | traces/2026-07-06_full-corpus-sweep_L001-L003.jsonl |
