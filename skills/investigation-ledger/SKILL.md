---
name: investigation-ledger
description: Maintain the investigation's single source of truth for leads, entities checked, queries run, and cold threads, plus a human-decision log. Use at the start of every investigation session (read state), at any lead status change, and at session end (commit updates) so no session ever starts cold and no thread is silently lost.
model: inherit  # deliberate: bookends every session's turns; an override would re-model the rest of the calling turn
---

# Investigation Ledger

> STATUS: skeleton — validate against the Agent Skills spec and flesh out during Phase 0.

Manages `LEDGER.md` (leads / entities checked / queries run / cold threads) and `DECISIONS.md`
(human-judgment log) at the repo root.

## Discipline

- Status machine: `open → triaged → investigating → verified | dead`; `parked` (cold) with revisit trigger.
- Single-writer: sub-agents return candidate rows; only the orchestrating session commits.
- Mid-stream leads enter as `open`; reconsidered at each triage checkpoint.
- Named-actor rule: no actor + date + record ID → cannot pass triage.

## Usage

```bash
python scripts/ledger_lint.py LEDGER.md   # schema check (columns, status values, dangling ids)
```
