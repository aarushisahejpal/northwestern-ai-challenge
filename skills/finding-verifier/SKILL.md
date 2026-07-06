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

## Protocol (claim verification)

1. The verifying agent gets claims + citation keys only — no drafting-session reasoning.
2. Record-level claims: open each cited record via `show_record.py` and re-derive the claim.
3. Aggregate claims: re-run the cited SQL from `queries/`; spot-check ≥3 sampled underlying records.
4. Verdicts: `verified` | `attribution error` (re-cite) | `overstated` (hedge) | `fabricated` (drop).
5. Headline check: does the headline claim more than the verified claims cumulatively show?
6. Lock only on pass; log the lock in `DECISIONS.md`.

## Protocol (outside-data checks: novelty / news-landscape)

Before investing more time in a lead, or presenting a finding's core mechanism as a
discovery, check what's already been reported. `scripts/ocr_pdf.py` supports OCR of
outside-source PDFs (e.g. court complaints) as part of the same discipline.

1. **Anchor the search window to the actual event date, not today.** State the
   period being checked before searching. Documented mistake (2026-07-06): searched
   "GlobalFoundries news 2026" for an event that happened in November 2024, and got
   irrelevant results until corrected to search that actual window.
2. **Run two distinct check types, not one blended search:**
   - *Novelty/prior-art check* — narrow queries combining the SPECIFIC named entities
     with the SPECIFIC angle/mechanism ("has anyone connected X's lobbying to Y's
     ownership"). Answers: is this already scooped?
   - *Landscape check* — broader queries on the entity alone, no angle. Surfaces
     adjacent context (other controversies, active reporting beats, enforcement
     history) that can sharpen or complicate a finding even when the specific angle
     isn't covered.
3. **Bound it: ~3 queries in parallel per check, one follow-up round max.** If still
   unresolved, note what's unconfirmed and move on rather than iterating indefinitely.
4. **WebFetch only to verify a specific snippet** (e.g. confirming an article's actual
   angle after a search summary flags it relevant) — not as a first resort.
5. **Distill to a conclusion before it reaches the ledger.** Record what's covered,
   what isn't, and the framing implication — not raw search output — in the lead's
   row, with source URLs for traceability.
6. **Log it as evidence, not a triage decision.** A novelty/landscape check informs
   whether and how to pursue a lead; it doesn't decide it. Chase/park/frame calls stay
   with the human, same as any other triage moment.
