---
name: dataset-primer
description: Bounded outward research to orient on an unfamiliar dataset before building against it — the "how does this data actually work, and what will silently corrupt my results?" scan. Runs a five-axis web scan (authoritative source + data dictionary; tribal-knowledge gotchas; open-source tooling; cleaned/derived datasets; access mechanics + licensing) against a fixed nine-category data-quality checklist (coverage; grain/double-counting; entity resolution; versioning/amendments; time semantics; denominators; suppression; authoritative-vs-derived; join keys) and emits a tiered, task-tailored reference brief cached in reference/ (refreshed, not re-researched). First-contact and targeted modes. A starting orientation, NOT a verification gate — every trap surfaced is a hypothesis to test. Sibling to outside-context-scan. Use when starting on a data source you haven't worked before, when a build depends on data whose cleanliness you haven't vetted, or when onboarding someone to a dataset.
model: sonnet  # bounded web research; the brief is hypotheses-not-gospel — mid-tier is the right spend
---

# Dataset Primer

On invocation, first tell the user: "Model override active — running at sonnet for the rest
of this turn." (This skill sets `model: sonnet` in its frontmatter; the override lasts until
the turn ends.)

Orient on an unfamiliar dataset *before* you build against it. The failure this skill exists to
prevent is the one everyone hits once: you wire up a data source, the query runs, the numbers look
clean — and only later (sometimes never) do you discover the itemization threshold, the
amended-filing duplicates, or the memo-code double-count that quietly corrupted every rollup. The
traps are almost always *known* — documented in a file dictionary, a NICAR talk, or a GitHub issue —
by someone who hit them first. This skill goes and finds them, on a fixed method, and writes them
down.

It is the inward-facing sibling of `outside-context-scan`: that one scans the public record to ask
"is this lead already reported?"; this one scans the public record to ask "how does this dataset
work, and where will it lie to me?" Same bounded-WebSearch discipline, same distill-to-a-written-
artifact ending, same explicitly-not-a-verification-gate posture.

## Check the library first

Before researching anything, look in `reference/` for an existing brief on this dataset. If one
exists, read it and only re-run the axes below to *refresh* what's stale (libraries move, coverage
windows extend) — don't re-research from zero. If none exists, produce one and save it there.

## Pick the mode

- **First-contact (default when there's no task yet)** — you're about to start working a dataset and
  want the full lay of the land. Produce the complete brief.
- **Targeted (when you have a specific operation)** — "I need to sum contributions by donor," "I need
  to join providers across two files." Same method, but the brief opens with *that* task and the
  gotchas table is filtered to the traps that bite *that* operation. This is where the value is: the
  FEC brief's single most important line — corporate donors live in the `oth` file, not `indiv`, so
  an individuals-only filter silently drops them — only surfaced *because* the task was "reconcile
  who gave to a Super PAC." A generic "here's the FEC dataset" dump would have buried it.

## The five search axes

Run bounded, like outside-context-scan: ~3 parallel queries per axis, one follow-up round max. If an
axis stays unresolved, note what's open and move on rather than iterating forever.

1. **Authoritative source + data dictionary** — the official record layout, field definitions, and
   the coverage statement. Ground truth; read it first.
2. **Tribal-knowledge gotchas** — the "everyone who works with this knows X" material that is *not*
   in the official docs: journalist/practitioner writeups, NICAR/IRE talks, blog posts, GitHub
   issues. Highest-value, least-Googleable axis — spend the most effort here.
3. **Open-source tooling** — parsers, API clients, loaders. Note what's actively maintained.
4. **Cleaned / derived datasets** — academic or third-party normalized versions (e.g. DIME for FEC).
   Usually a *benchmark* to check your own work against, not the source of truth to ingest.
5. **Access mechanics + licensing** — API vs bulk, keys, rate limits, cost, and terms-of-use
   restrictions (some data is legally restricted in how it may be used).

## The nine-category data-quality checklist

The core of the skill. The same categories of trap recur across every dataset, so the brief must
answer each one *for this dataset* — instantiate the row, don't just restate it. If the honest
answer is "n/a here," say so; a blank means you didn't check.

| Category | The question | Recurs as (cross-domain examples) |
|---|---|---|
| Coverage boundaries | What's deliberately in vs. out? | FEC $200 itemization floor · court sealed/expunged, PACER gaps · CMS Advantage claims absent, cell suppression <11 |
| Grain / double-counting | What does one row mean; where do sums overcount? | FEC conduit memo rows · CMS line vs claim vs beneficiary · court docket entries vs cases |
| Entity resolution | Stable IDs, or free-text names? | FEC employer/name free-text · CMS NPI (type-1/2, reassignment) · court party/firm name variants |
| Versioning / amendments | How are records superseded/restated? | FEC amendments (keep latest) · CMS adjustments/voids (final-action) · docket corrections |
| Time semantics | Which of several dates do you mean? | filing vs transaction date · service vs paid date · docket-entry vs decision date |
| Denominators | Do counts need a base for rates? | CMS enrollment denominators, risk adjustment · court caseload per judge |
| Suppression / privacy | What's hidden or legally restricted? | FEC ban on donor-data solicitation use · HIPAA / cell suppression · court PII redaction |
| Authoritative vs. derived | Official record vs. cleaned copy? | FEC paper-report precedence · PACER (authoritative, paid) vs RECAP (free, may lag) · raw claims vs Public Use Files |
| Join keys / crosswalks | What's the glue, and is it stable? | committee ID / CIK · NPI / CCN / HCPCS · FIPS / GEOID · docket-number formats vary by court |

## The output brief (template)

Same skeleton every time, so nothing gets skipped and every brief reads alike:

1. **Task & framing** — what you're using the data for; the one or two structural facts that reframe
   everything (for FEC: "LD-203 and FEC are different universes; you're looking for gaps, not
   equality").
2. **Access & credentials** — endpoint/bulk, keys (env-var only, never committed), rate limits, cache
   location, licensing.
3. **Structural trap(s)** — the one or two things most likely to silently break *this* task, called
   out above the fold.
4. **Data-quality table** — the nine-category checklist, instantiated for this dataset.
5. **Tiered resources** — Tier 1 authoritative, Tier 2 tooling, Tier 3 practitioner/derived — each an
   annotated link.
6. **Recommended sequence** — the order to read/test in, ending with "pull a small real sample and
   test each trap before trusting."
7. **Conventions** — where outputs/caches go, how the data is cited.

## Two rules that keep it honest

- **Task-tailoring is mandatory.** A brief that isn't anchored to what you're doing buries the one
  trap that matters. Always open with the task.
- **The brief is hypotheses, not gospel.** Every trap ends with "verify against a real sample." This
  is a bounded starting aid, not a verification gate — it orients you; the data validates. Never let
  a brief's claim substitute for looking at real rows.

## Save it

Write the finished brief to `reference/<dataset-slug>.md` and add a row to `reference/README.md`. The
library compounds: the second person to touch the dataset gets the brief instantly instead of
re-learning the traps the hard way.

Worked example: `reference/fec-campaign-finance.md` — the FEC campaign-finance brief that informed
`skills/lead-scanner/scripts/fec_enrich.py`.

No custom script — this is a documented discipline for using WebSearch/WebFetch directly, the same
way `outside-context-scan` and `lead-scanner` document disciplines rather than automate them.

## Turn discipline

When the brief is saved to `reference/` and indexed, report where it landed and end the turn.
The model override lasts the rest of the turn, so don't continue into the build the brief was
for — start that on a fresh prompt, at the session's own model.
