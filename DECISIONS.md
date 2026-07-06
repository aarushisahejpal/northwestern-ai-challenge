# Decision Log — human-judgment moments

Required by the brief: interaction traces must show "the moments where human judgment intervened."
Every human intervention — triage selections, lead kills, editorial calls, legal-flag decisions,
scope changes — gets a row. Referenced from README §3 and from each finding's verification block.

**Fresh start (2026-07-06, second attempt):** reset a second time alongside LEDGER.md. The first
full-corpus attempt (archived at `archive/DECISIONS_full-sweep-rediscovery_2026-07-06.md`) mostly
re-derived findings already on file from the pilot pass, because it ran the same canned lens file
that originally produced them. The pilot-era decision history is separately archived at
`archive/DECISIONS_pilot-triage_2026-07-06.md`.

| date | decision | rationale | who | trace file |
|---|---|---|---|---|
| 2026-07-06 | Generated leads only from self-designed rate-of-change / emergence / contribution-flow lenses (new file `queries/emergence_and_flows.sql`); did not run any `sweep_2026.sql` block | The prior full-corpus attempt replayed the canned sweep and re-derived known anomalies; independent generation requires querying dimensions the sweep doesn't cover (trends over 2022-2026, individuals-as-clients, contribution flows, single-quarter spikes) | orchestrator | 2026-07-06_generation_emergence-flows.jsonl |
| 2026-07-06 | Set aside the mechanically-dominant top of each lens (Korea Zinc atop E1; Trump-Vance inaugural donors and the IBEW "N/A" placeholder atop F1) and promoted the mid-tier instead | Per the brief's "dig past the top-of-list" instruction: the single biggest number in a simple ranking is a surface artifact, not a finding. Korea Zinc is a known takeover fight; inaugural giving is a widely-reported category | orchestrator | 2026-07-06_generation_emergence-flows.jsonl |
| 2026-07-06 | Killed the original E2 design (a global "firms-per-client" fan-out ranking) and replaced it with an honest per-client roster drill | Client identity fragments across registrants — Senate `client_id` is registrant-scoped, and both the entity resolver and name-normalization split Vantive and TP-Link into multiple keys. A global GROUP BY would have produced clean-looking but wrong firm counts (this repo's documented failure mode). The defensible firm-count is read from the roster per client | orchestrator | 2026-07-06_generation_emergence-flows.jsonl |
| 2026-07-06 | Flagged L021 (Daibes clemency lobbying) and L023 (Vantive → White House Ballroom Project) for an editorial/legal-sensitivity review before any finding is locked | Both name living individuals and touch an active clemency ask / a project associated with the sitting President; consistent with treating legal-flag calls as a human (Rob) decision as on L003. The underlying records are public, so the leads are logged, but publication framing needs the flag cleared | orchestrator (flag pending, Rob) | 2026-07-06_generation_emergence-flows.jsonl |
| 2026-07-06 | Logged the raw corpus being absent on this box (only `db/lda_full.duckdb` present) as a verification constraint, not a blocker | Leads carry stable DB-resolved citation keys (`filing_uuid` / `filing_id` / `src_file:src_line`), which are the sanctioned identifiers; the raw-record round-trip via `show_record.py` is deferred until `data/` is re-materialised for lock-time re-derivation | orchestrator | 2026-07-06_generation_emergence-flows.jsonl |
