---
name: outside-context-scan
description: Exploratory web research in two modes — a live scan for whether a lead's angle is already reported (novelty/prior-art) and the current picture on an entity (news-landscape), and a date-gated contemporaneous scan for what the public record looked like at the time of a past event (salience-at-passage, say-vs-pay). Informal and bounded, not a verification gate; does not confirm or refute any claim in this project's own data. Use during triage, before or alongside drafting, never as a substitute for skills/finding-verifier for claims that need locking.
---

# Outside Context Scan

Exploratory research using outside sources (WebSearch/WebFetch), not corpus verification.
It answers triage-relevant questions before a lead absorbs more time — but *which*
question you're asking determines *how* you search, and getting that fork wrong is the
failure mode this skill exists to prevent. Results inform a chase/park/frame decision —
they never verify or lock anything from this project's own findings; that's
`skills/finding-verifier`'s job, and the two shouldn't be conflated (a past version of
this protocol lived inside finding-verifier and overstated its rigor by association —
moved out for that reason, 2026-07-06).

## Pick the question; the question picks the mode

Two different questions need two different searches. Choosing the wrong one is the
documented mistake below, so decide before querying:

- **Live scan (default) — "Is this already reported? What's the current picture on this
  entity?"** You *want* the live index and recency here; if someone published your exact
  angle last month, that is the most important thing to find, and date-gating would hide
  it. No date restriction.
- **Contemporaneous scan (opt-in) — "What did the public record look like *at the time*
  of the event?"** You *must* restrict to the event window; recency is noise. Use this
  only when the finding's logic depends on the state of the world at a past date —
  salience at the moment of passage, say-vs-pay contrasts, "silent when it mattered."

Both documented failures of this protocol were the same error — running a live/recency
search on a contemporaneous question: "GlobalFoundries news 2026" for a November-2024
event (2026-07-06), and a SECURE-2.0 salience read that pulled 2023–2025 retrospectives
instead of December-2022 coverage (2026-07-07). Naming the fork is the fix; a year in the
query string is not a date filter (it matches pages that *mention* the year, which are
mostly later retrospectives).

## Live scan mechanics (default)

Run two distinct check *types*, not one blended search:
- *Novelty/prior-art check* — narrow queries combining the SPECIFIC named entities with
  the SPECIFIC angle/mechanism ("has anyone connected X's lobbying to Y's ownership").
  Answers: is this already scooped?
- *Landscape check* — broader queries on the entity alone, no angle. Surfaces adjacent
  context (other controversies, active reporting beats, enforcement history) that can
  sharpen or complicate a finding even when the specific angle isn't covered.

## Contemporaneous scan mechanics (opt-in)

State the window (the actual event date plus the run-up/aftermath you care about) before
searching, then *enforce* it — stating it is not enough:

- **GDELT DOC 2.0 API is the reliable date filter** — it filters on *publish* date, not page
  content. Fetch
  `https://api.gdeltproject.org/api/v2/doc/doc?query=<terms>&startdatetime=YYYYMMDDHHMMSS&enddatetime=YYYYMMDDHHMMSS&maxrecords=<=250>&sort=dateasc&mode=artlist&format=json`.
  `sort=dateasc` surfaces the first wave (run-up/passage); `mode=timelinevol` returns a
  volume-over-time curve — the honest way to read "how loud was this, and when." Caveat:
  GDELT indexes roughly 2017 to present; it is blind to older events.
  - *Fetch mechanics (verified 2026-07-07):* WebFetch often returns **HTTP 429** on this
    endpoint — GDELT rate-limits by IP and WebFetch shares one. Fall back to a **direct
    `curl`** of the identical URL (public JSON, no auth) written to a file, then parse the
    JSON yourself: cleaner than the WebFetch model layer for `timelinevol`/`artlist`, and it
    dodges the rate limit. Quote the URL and pass a plain user-agent. This is still "the
    GDELT fetch is the search," just via curl, not WebFetch.
- **WebSearch date operators** (`after:YYYY-MM-DD before:YYYY-MM-DD`) bias toward the
  window but are a soft filter, not a hard cut — pair them with event verbs ("passes",
  "clears", "signs") and drop the bare year from the query string.
- **allowed_domains** to the outlets that covered the beat in real time focuses the scan
  further; combine it with the date restriction, don't rely on it alone.

## Shared discipline (both modes)

1. **Bound it: ~3 queries in parallel per check, one follow-up round max.** If still
   unresolved, note what's unconfirmed and move on rather than iterating indefinitely.
2. **WebFetch on a page only to confirm a specific snippet** (e.g. verifying an article's
   actual angle after a search summary flags it relevant) — not as a first resort. The
   GDELT fetch above is the one exception: there it *is* the search, not a follow-up.
3. **Distill to a conclusion before it reaches the ledger.** Record what's covered, what
   isn't, and the framing implication — not raw search output — in the lead's row, with
   source URLs for traceability.
4. **Log it as evidence, not a triage decision.** A scan informs whether and how to
   pursue a lead; it doesn't decide it. Chase/park/frame calls stay with the human, same
   as any other triage moment.

No custom script — this is a documented discipline for using the WebSearch/WebFetch tools
directly, the same way `lead-scanner`'s discipline governs SQL-first scans over the
internal corpus. Think of the two as a pair: one scans inward (the database), this one
scans outward (the public record).
