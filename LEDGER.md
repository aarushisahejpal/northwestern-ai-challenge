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

## Leads

| id | hypothesis (one line) | lens | named actors | status | owner | evidence so far (record IDs) | next action | updated |
|---|---|---|---|---|---|---|---|---|
| L001 | — | — | — | open | — | — | — | — |

## Entities checked

| entity (entity_id) | verdict | records examined | date |
|---|---|---|---|
| — | — | — | — |

## Queries run

| date | SQL (file in queries/) | one-line result |
|---|---|---|
| — | — | — |

## Cold threads

| lead id | parked reason | revisit trigger | date parked |
|---|---|---|---|
| — | — | — | — |
