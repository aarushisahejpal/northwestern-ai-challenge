---
name: finding-verifier
description: Independently re-derive every claim in a draft finding before it locks. A fresh agent receives the claims with citation keys but without the drafting session's reasoning, opens each cited record itself, re-runs cited SQL for aggregate claims, and issues a per-claim verdict (verified, attribution error, overstated, fabricated). Use before any finding is locked or published.
---

# Finding Verifier

> STATUS: skeleton — validate against the Agent Skills spec and flesh out during Phase 4.

Input: one finding file (locked-finding shape) + `db/lda.duckdb` + raw corpus.
Output: a verification block appended to the finding, with a verdict per claim.

## Protocol

1. The verifying agent gets claims + citation keys only — no drafting-session reasoning.
2. Record-level claims: open each cited record via `show_record.py` and re-derive the claim.
3. Aggregate claims: re-run the cited SQL from `queries/`; spot-check ≥3 sampled underlying records.
4. Verdicts: `verified` | `attribution error` (re-cite) | `overstated` (hedge) | `fabricated` (drop).
5. Headline check: does the headline claim more than the verified claims cumulatively show?
6. Lock only on pass; log the lock in `DECISIONS.md`.
