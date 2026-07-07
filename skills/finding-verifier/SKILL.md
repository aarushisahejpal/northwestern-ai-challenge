---
name: finding-verifier
description: Independently re-derive every claim in a draft finding before it locks. A fresh agent receives the claims with citation keys but without the drafting session's reasoning, opens each cited record itself, re-runs cited SQL for aggregate claims, and issues a per-claim verdict (verified, attribution error, overstated, fabricated). Use before any finding is locked or published.
---

# Finding Verifier

Input: one finding file (locked-finding shape) + a built DuckDB + raw corpus.
Output: a verification block appended to the finding, with a verdict per claim.

Exercised twice (2026-07-06, L010): first pass returned FAIL and caught two real
overreaches (an uncited ownership-relationship claim, an overstated aggregate); second
pass, after fixes, returned PASS. Both runs were fresh agents with no drafting-session
context, per the protocol below.

For checking whether a lead's angle is already reported elsewhere (exploratory outside
research, not claim verification), see `skills/outside-context-scan/SKILL.md` instead —
that's a lighter-weight, earlier-stage discipline and shouldn't be confused with this one.

## Protocol (claim verification)

1. The verifying agent gets claims + citation keys only — no drafting-session reasoning.
2. Record-level claims: open each cited record via `show_record.py` and re-derive the claim.
3. Aggregate claims: re-run the cited SQL from `queries/`; spot-check ≥3 sampled underlying records.
4. Verdicts: `verified` | `attribution error` (re-cite) | `overstated` (hedge) | `fabricated` (drop).
5. Headline check: does the headline claim more than the verified claims cumulatively show?
6. Lock only on pass; log the lock in `DECISIONS.md`.

When a claim depends on a document *outside* the corpus (e.g. a court complaint or SEC
filing), use `skills/source-document-reader` to turn that PDF into page-anchored, citable
text, then apply the exact verdict discipline above to the specific claim against the
specific text. That skill owns the OCR mechanics and the external-document citation
convention; this skill owns the verdict.
