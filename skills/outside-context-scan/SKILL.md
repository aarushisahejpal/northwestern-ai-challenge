---
name: outside-context-scan
description: Exploratory web research to check whether a lead's angle is already covered elsewhere (novelty/prior-art) and to surface adjacent context about a named entity (news-landscape) — before investing more time drafting a finding. Informal and bounded, not a verification gate; does not confirm or refute any claim in this project's own data. Use during triage, before or alongside drafting, never as a substitute for skills/finding-verifier for claims that need locking.
---

# Outside Context Scan

Exploratory research using outside sources (WebSearch/WebFetch), not corpus verification.
Answers two triage-relevant questions before a lead absorbs more time: has this already
been reported, and what else is publicly known about the entities involved. Results
inform a chase/park/frame decision — they never verify or lock anything from this
project's own findings; that's `skills/finding-verifier`'s job, and the two shouldn't be
conflated (a past version of this protocol lived inside finding-verifier and overstated
its rigor by association — moved out for that reason, 2026-07-06).

## Protocol

1. **Anchor the search window to the actual event date, not today.** State the period
   being checked before searching. Documented mistake (2026-07-06): searched
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
6. **Log it as evidence, not a triage decision.** A scan informs whether and how to
   pursue a lead; it doesn't decide it. Chase/park/frame calls stay with the human,
   same as any other triage moment.

No custom script — this is a documented discipline for using the WebSearch/WebFetch
tools directly, the same way `lead-scanner`'s discipline governs SQL-first scans over
the internal corpus. Think of the two as a pair: one scans inward (the database), this
one scans outward (the public record).
