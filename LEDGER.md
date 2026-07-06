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

**Fresh start (2026-07-06, second attempt):** this ledger was reset a second time. The first
full-corpus attempt ran `queries/sweep_2026.sql` wholesale and, unsurprisingly, re-derived the same
top-line anomalies already documented in the pilot archive (a self-reported vanity filing at the top
of spend rankings; a foreign-owned semiconductor company's disclosed ownership) — re-running the
exact SQL that originally found those things just re-finds them, it isn't independent generation.
That attempt is archived at `archive/LEDGER_full-sweep-rediscovery_2026-07-06.md`. The prior pilot
pass is separately archived at `archive/LEDGER_pilot-triage_2026-07-06.md`. This ledger starts empty
again for a session designing its own exploratory queries rather than replaying `sweep_2026.sql`.

## Leads

| id | hypothesis (one line) | lens | named actors | status | owner | evidence so far (record IDs) | next action | updated |
|---|---|---|---|---|---|---|---|---|

## Entities checked

| entity (entity_id) | verdict | records examined | date |
|---|---|---|---|

## Queries run

| date | SQL (file in queries/) | one-line result |
|---|---|---|

## Cold threads

| lead id | parked reason | revisit trigger | date parked |
|---|---|---|---|
