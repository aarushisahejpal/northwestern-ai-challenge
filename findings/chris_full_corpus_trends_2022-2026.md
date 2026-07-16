# Finding: Full-corpus Senate lobbying trends, 2022–2026 Q1 (ported from Chris Cioffi's findings report)

**Status:** author-verified AND fresh-agent verified — **PASS, 8/8 claims** (2026-07-14,
finding-verifier protocol; verification block appended at the end of this file, including
three hedges to carry when citing). LOCKED as a submitted finding (team sign-off, DECISIONS.md 2026-07-15).
**Author:** Chris Cioffi. Ported verbatim from `ChrisCioffi/agentic_investigation`
`skills/lobbying-issue-theme-clustering/FINDINGS.md` (sections reproduced unchanged; only this
provenance header added).
**Produced with:** `skills/lobbying-quarterly-filings/` (migrated into this repo) —
`get_local_senate_filings()` per year + `flag_dupes()` + `flag_client_registrant_conflict()`.
The original report's TAX-theme section used the `lobbying-issue-theme-clustering` skill,
which is NOT part of this submission, and is deliberately not ported (except the
double-counting-trap subsection below, whose fix and root-cause trace live in this repo at
`skills/lobbying-quarterly-filings/scripts/lobbyr_clean.R` (`normalize_entity_name()`) and
`skills/lobbying-quarterly-filings/references/data_quality_notes.md`).
**Legal flag:** none
**Cross-corroboration note (added at port):** the "STATE OF LOC NATION" $20M×3 suspicious
filings flagged below were independently flagged by this repo's own pipeline (leads
L025/L027, `traces/INDEX.md`) — two toolchains, same anomaly.

---

### (from the TAX section) A real double-counting trap

**A real double-counting trap, caught by hand -- and fixed, not just flagged.** "Business
Roundtable" appears under five spellings in this data -- "BUSINESS ROUNDTABLE", "THE BUSINESS
ROUNDTABLE", "THE BUSINESS ROUNDTABLE, INC.", "BUSINESS ROUNDTABLE INC", and "BUSINESS
ROUNDTABLE (THE)" -- across its own $7.59M self-filed report *and* separate outside-firm
filings (Ballard Partners, CGCN Group, Fierce Government Relations, Invariant, Mehlman
Consulting, PricewaterhouseCoopers, S-3 Group, Duberstein Group, Williams & Jensen, and
others; ~$60K-120K each). The root cause turned out to be more specific than "inconsistent
spelling across filings": Business Roundtable's *own* self-filed row has `registrant.name` =
"THE BUSINESS ROUNDTABLE, INC." but `client.name` = "BUSINESS ROUNDTABLE INC" -- **not
identical even within its own single filing**, in any of the 5 years on file. Since
`flag_client_registrant_conflict()`'s self-lobbying detection requires those two fields to
match, and the original normalization only stripped punctuation/case (not words like
"The"/"Inc."), the check never fired for this entity at all, in any year. This has now been
fixed (`normalize_entity_name()` in `scripts/lobbyr_clean.R` -- strips a conservative,
whole-word legal-suffix list) and verified: all outside-firm Business Roundtable filings are
now correctly recognized as double-counting and removed, while the true self-filed row is
kept, and the several genuinely distinct regional/topical Business Roundtables (Gulf South, Ohio,
Colorado, Arizona, American Turkish, Small Business Roundtable) are correctly left untouched. This was never unique to Business Roundtable
-- re-running the fixed function against the full multi-year corpus (see the next section)
caught 13,269 additional double-counting rows corpus-wide that the original logic had
silently missed. Full root-cause trace and validation methodology in
`references/data_quality_notes.md` *[in this repo: `skills/lobbying-quarterly-filings/references/data_quality_notes.md`]*.

---

## Full-corpus lobbying trends, 2022-2026 (Q1)

**Data**: Every Senate quarterly filing on disk, all years and all 79 lobbying issue areas
(ALI codes) present in the corpus -- not a single-issue slice like the TAX section above. *[porter's note: refers to the original report's TAX-quarter section, which is not part of this submission; only its double-counting-trap subsection is reproduced above — see the provenance header]*
2022, 2023, 2024: full years. 2025: full year. **2026: Q1 only** (the most recent quarter on
disk as of this report) -- every 2026 figure below is a single-quarter number, never
compared to a full-year figure without saying so explicitly.

**Methodology**: Loaded per-year via `get_local_senate_filings(years = y, tidy_result =
FALSE)` for y in 2022:2026 (bounds `pivot_wider()` cardinality per year rather than one
5-year combined pivot), id-like columns coerced to `character` before `bind_rows()` (some
years encode `client.client_id` etc. as integer, others as character), then cleaned via the
same `flag_dupes()` + `flag_client_registrant_conflict()` pipeline as the TAX section.*[porter's note: same cleaning pipeline as reproduced in the trap subsection above]* **418,098
raw filings -> 303,820 after cleaning.** *[porter's note: these figures were computed under the pipeline's pre-2026-07-15 rule, which dropped ALL termination filings; per the team decision logged in DECISIONS.md (2026-07-15), termination-filing income now counts when it is the quarter's only record, so a re-run with the current pipeline yields slightly HIGHER totals — the figures here are conservative]* Filings/distinct clients by year: 2022 (67,805 /
17,847), 2023 (69,352 / 18,255), 2024 (71,136 / 18,630), 2025 (77,894 / 20,900), 2026 Q1-only
(17,633 / 16,461). Issue-level columns were identified by matching against the actual ALI
code lookup (`list_ali_codes()`), not a hand-maintained exclusion list -- an early version of
this analysis misclassified ~127 real metadata columns (`registrant_country`, `client.state`,
etc.) as "issues" by using too short an exclusion list; re-deriving from the real code list
caught it. "Amount" = `coalesce(expenses, income)` per filing, same convention as the TAX
section, with the same multi-issue-filing double-counting caveat (a filing touching 3 issues
counts its full dollar amount toward each of the 3).

**Updated from an earlier pass of this report** (which had 317,089 cleaned filings) after
fixing a real bug in `flag_client_registrant_conflict()`'s entity matching -- see the TAX
section's "double-counting trap" finding above and `references/data_quality_notes.md` for the
full root-cause trace. The fix catches **13,269 additional double-counting rows corpus-wide**
that the original punctuation/case-only name matching silently missed -- this was never
unique to Business Roundtable. All figures below reflect the corrected, 303,820-filing
cleaned set; the overall trends and rankings are essentially unchanged from the earlier pass
(same winners, same losers, dollar totals modestly smaller), which is itself a useful
sanity check that the bug was a real but bounded double-counting leak, not something that was
distorting the corpus's big-picture shape.

Every finding below was checked against the underlying raw filings before being written down
-- several numbers that looked like blockbuster findings turned out to be name-variant
artifacts or single-quarter outliers once traced back to source, and are flagged as such
rather than reported at face value.

### Which issue area grew the most, 2022 -> 2025 (full years)?

There's no single "most growth" answer -- it depends on whether a journalist means dollars or
lobbying-client breadth, and absolute or relative terms. All four framings:

| Framing | Winner | 2022 | 2025 | Change |
|---|---|---|---|---|
| Absolute $ growth | **Trade (domestic/foreign)** | $1,282.2M | $1,521.8M | **+$239.6M** (+18.7%) |
| Relative $ growth (min $250k base) | **Tariff (miscellaneous tariff bills)** | $65.6M | $206.5M | **+215%** |
| Absolute client growth | **Budget/Appropriations** | 4,557 clients | 5,549 clients | **+992 clients** (+21.8%) |
| Relative client growth | **Tariff (miscellaneous tariff bills)** | 127 clients | 362 clients | **+185%** |

Runners-up by absolute dollars: Taxation/Internal Revenue Code (+$214.9M, +10.0%),
Budget/Appropriations (+$198.8M, +12.5%), Energy/Nuclear (+$171.6M, +22.9%), Agriculture
(+$156.2M, +49.2%). Tariff shows up as the runaway winner on every *relative* measure --
consistent with a live, escalating trade-policy story rather than steady-state lobbying.

### Which issue area grew the least (or shrank), 2022 -> 2025?

| Framing | "Loser" | 2022 | 2025 | Change |
|---|---|---|---|---|
| Absolute $ decline | **Disaster Planning/Emergencies** | $267.3M | $131.1M | **-$136.1M** (-50.9%) |
| Relative $ decline (min $250k base) | **Unemployment** | $93.8M | $11.4M | **-87.8%** |
| Absolute client decline | **Transportation** | 1,882 clients | 1,748 clients | **-134 clients** (-7.1%) |
| Relative client decline | **Civil Rights/Civil Liberties** | 274 clients | 193 clients | **-29.6%** |

Disaster Planning/Emergencies and Unemployment both read as pandemic-era wind-down stories:
2022 was still close to COVID-era emergency-relief and expanded-unemployment-benefit
legislative activity, and by 2025 most of that had lapsed or been resolved, so the lobbying
spend around it largely evaporated. Civil Rights/Civil Liberties losing nearly 30% of its
distinct lobbying clients in three years is worth a follow-up call to some of the
organizations that dropped off the list -- this dataset shows *that* it happened, not *why*.

### Emerging industries: who showed up in the lobbying corps for the first time?

The 79 ALI issue-area codes are all long-established umbrella categories (Trade, Defense,
Energy, etc.) -- none of them are literally brand-new, so "emerging industries" shows up
much more clearly at the **client level**: real companies with **$0 in lobbying spend in
2022** that appear as real, meaningfully-sized lobbying clients by 2025.

**Generative AI arrived as a K Street client class that didn't meaningfully exist in 2022.**
Anthropic PBC ($0 -> $3.12M), OpenAI Opco, LLC ($0 -> $2.99M), and a16z Capital Management ($0
-> $3.48M) all first appear as lobbying clients in this window -- a concrete, dated marker of
when frontier AI labs and their investors started actively lobbying Congress.

**A parallel wave of foreign trade/critical-minerals/EV-supply-chain entrants**, plausibly
tariff- and industrial-policy-driven: Nippon Steel ($0 -> $3.42M -- during its high-profile
bid for U.S. Steel), Korea Zinc ($0 -> $2.53M), Hanwha Q Cells America (solar, $0 -> $3.10M),
Gotion Inc. (EV batteries, $0 -> $2.46M), and SK Americas ($0 -> $5.77M). None of these
companies is new to the world -- they're new to *this dataset*, meaning 2022 was the first
time each had no federally-disclosed U.S. lobbying presence and 2025 is the first time they
did. (Tencent America was in an earlier pass of this list, but doesn't belong there -- properly
name-normalized, it already had $800K in 2022 lobbying spend, growing to $4.04M by 2025; it's
a real grower, not a first-time entrant, and was dropped once that was caught.)

### Registrants and clients that upped their spending

**Important correction made during this analysis**: a naive name-based ranking initially
showed "Ballard Partners" appearing from $0 (2022) straight to $69.6M (2025) as a brand-new
registrant -- but tracing it back, "BALLARD PARTNERS, LLC" (2022-2024, 2026) and "BALLARD
PARTNERS" (2025 only, no "LLC" suffix) are the same real firm; it simply dropped the suffix
in its 2025 filings. This is a different problem from the Business Roundtable bug above (that
one was registrant-name-vs-client-name mismatch within a single filing; this one is one
registrant's own name drifting across years) -- but the same fix applies: the table below is
computed with `normalize_entity_name()` (the same helper `flag_client_registrant_conflict()`
now uses, applied here to roll up one registrant/client's totals across its own name history)
so this mistake isn't repeated.

**Top registrant increases, 2022 -> 2025 (name-normalized):**

| Registrant | 2022 | 2025 | Change |
|---|---|---|---|
| Ballard Partners | $15.70M | $68.07M | **+$52.37M** (+334%) |
| Miller Strategies | $4.98M | $28.32M | +$23.34M (+469%) |
| BGR Government Affairs | $27.42M | $49.91M | +$22.49M (+82%) |
| Continental Strategy | $0.31M | $20.84M | +$20.52M (+6,600%) |
| Mercury Public Affairs | $5.48M | $21.01M | +$15.53M (+283%) |
| Business Roundtable | $20.41M | $33.50M | +$13.09M (+64%) |
| Cornerstone Government Affairs | $25.28M | $37.82M | +$12.54M (+50%) |
| General Motors (self-filed) | $10.05M | $21.39M | +$11.34M (+113%) |

Both of the two most extreme movers were individually verified against raw filings, not just
trusted at face value: **Miller Strategies** grew from 44 distinct clients (2022) to 127
(2025) -- a genuinely broad, blue-chip roster (SpaceX, OpenAI, Oracle, Morgan Stanley, General
Motors, Charter Communications, Dow Chemical, SoftBank, several city governments) rather than
one large client inflating the total. **Continental Strategy**, up more than 60x, grew from
11 filings/handful of clients in 2022 to 318 filings in 2025 across a large, real, named
client list (American Association of Homecare, Applied Materials, Anthropic, American Sugar
Refineries, and dozens more) -- a genuine scale-up of a Florida/DC lobbying shop, not a
duplication artifact.

**Top client increases, 2022 -> 2025 (name-normalized):** Business Roundtable (+$13.09M,
+64%), General Motors (+$11.34M, +113%), PhRMA (+$9.61M, +34%), Meta Platforms (+$6.95M,
+36%), UnitedHealth Group (+$5.34M, +94%).

### Registrants and clients whose spending diminished

**Top registrant/client decreases, 2022 -> 2025:** SAP America (-$128.7M, -97%), National
Association of Realtors (-$27.4M, -34%), Alzheimer's Association (-$10.75M, -73%), Chamber of
Commerce of the USA (-$9.1M, -12%), Biotechnology Innovation Organization (-$7.66M, -58%).
(These five are unchanged by the cleaning fix -- none of them had a self-filed-report /
outside-firm double-counting relationship, so their totals were already correct.)

**A blockbuster-looking number that turned out to be a single-quarter outlier, caught by
hand.** SAP America's headline "$132.35M -> $3.62M, a 97% cut" does not reflect a real
spending pullback. Tracing the 2022 filings individually: SAP America self-filed $1.04M,
$610K, and $610K in three of 2022's four quarters -- completely in line with 2023-2025's
run rate -- but its **Q2 2022** filing alone reports **$130.09M** in expenses
(`filing_document_url` links directly to that filing). That one anomalous quarter, not a
genuine multi-year decline, is responsible for the entire "$128.7M drop." The real story, once
that outlier is set aside, is that SAP America's lobbying spend has been flat, not
collapsing -- exactly the kind of number a journalist should trace to source before citing,
which is why `filing_document_url` is in every fact-check table this project produces.

### The 2025 tax bill: what spiked, and has it tapered off in 2026?

Comparing each issue's **Q1 dollar total** across years isolates a same-quarter,
apples-to-apples comparison: baseline = average of Q1 2022/2023/2024, "spike" = Q1 2025 vs.
that baseline, "taper" = Q1 2026 vs. Q1 2025.

The core tax-and-budget cluster shows the expected shape -- a real but modest bump around the
reconciliation bill's passage, already easing off one quarter later:

| Issue | Q1 baseline (avg '22-'24) | Q1 2025 | Q1 2026 | Spike | Taper |
|---|---|---|---|---|---|
| Taxation/Internal Revenue Code | $528.7M | $620.0M | $567.7M | +17.3% | **-8.4%** |
| Agriculture | $91.8M | $119.9M | $113.7M | +30.6% | **-5.2%** |
| Law Enforcement/Crime/Criminal Justice | $72.2M | $95.1M | $87.0M | +31.6% | **-8.5%** |
| Railroads | $31.7M | $37.9M | $17.3M | +19.5% | **-54.5%** |

Railroads posted by far the sharpest snap-back -- Q1 2026 spend is less than half its Q1 2025
level and below its pre-2025 baseline, consistent with a issue that surged for one
bill-passage cycle and genuinely receded once it was resolved.

**But tariffs are the counter-example -- they did not taper, they kept climbing.** Tariff
(miscellaneous tariff bills) spiked +153% in Q1 2025 ($16.4M baseline -> $41.5M) and then
climbed *another* 37.2% in Q1 2026, to $57.0M -- the opposite of the "spike then recede"
pattern the tax bill produced. Apparel/Clothing Industry/Textiles is the one issue that
matches the full "spiked hard, then genuinely tapered" pattern almost exactly (+61.4% in Q1
2025, then -44.8% in Q1 2026) -- plausibly downstream of the same tariff fight, but resolved
faster and on a much smaller base ($1.5M baseline). The honest answer to "what spiked in 2025
and has now tapered off": **the tax-and-budget-adjacent issues did (Taxation, Agriculture, Law
Enforcement, Railroads most sharply), but trade/tariff issues have not** -- they're still an
active, escalating story a full year later, not a one-time bill-passage spike.

### Three more questions a journalist might ask

**Q: Is there a filing in this dataset that looks too big to be real?**
Yes -- worth a direct call before anyone cites it. **"STATE OF LOC NATION GLOBAL PUBLIC
BENEFIT CORPORATION"**, lobbied by registrant "LOC Community Association," reports exactly
**$20,000,000 in expenses in each of Q2, Q3, and Q4 2025** ($60M for the year) -- a
suspiciously round, suspiciously repeated figure from two obscure, hard-to-place entity names
that otherwise don't show up anywhere else in the corpus. That would place this single
client/registrant pair's 2025 spend on par with the Chamber of Commerce's entire annual
self-filed total. It may be entirely legitimate, but the combination of an exact repeated
round number and unfamiliar entity names is exactly the profile worth fact-checking against
the source filings (`filing_document_url`) before repeating the number in print.

**Q: Which single K Street firm's business grew the fastest, and is the growth durable or a
blip?** Continental Strategy, LLC (see above) -- 11 filings/small client roster in 2022 to
318 filings across dozens of named, verifiable clients in 2025, sustained (not reversed) into
2026 ($8.16M in Q1 2026 alone, on pace with a full 2025 of $20.8M). This reads as a real,
durable scale-up of one firm's book of business, not a one-quarter fluke.

**Q: Beyond AI, which entirely new client shows up lobbying on the most distinct issue areas
in its very first year in the data?** Worth a follow-up pull the next time this dataset is
refreshed -- this section focused on total-dollar new entrants; cross-referencing "new since
2022" clients against breadth-of-issue-area (the same lens the Business Roundtable/Altria
findings above used for the TAX-only slice *[porter's note: the Altria breadth finding lives in the original report's TAX section, not ported here]*) across the full 79-issue corpus is a natural
next step once a similar per-issue-per-client breadth table is built for all years, not just
one quarter.

---

# Verification block (finding-verifier protocol, 2026-07-14)

**Verdict: PASS — 8/8 claims verified.** Fresh agent, no drafting-session context, re-derived
each claim against `db/lda_full.duckdb` + raw corpus with 4 record spot-checks via
`show_record.py`. Full verdict table below; three hedges to carry when citing this finding:

1. **"First appearance" framing (AI clients):** Anthropic, OpenAI, and a16z all first appear
   as lobbying clients in **2023**, ramping to ~$3M-scale by 2025. Accurate framing: "absent
   in 2022, ramping from 2023" — not "first appears in 2025." (2025 self-filed totals verified
   to the dollar: Anthropic $3.12M exact, OpenAI $2.99M exact, a16z $3.53M vs claimed $3.48M.)
2. **Snapshot vintage (conservative bias):** the report's pipeline snapshot predates
   late-posted Q4-2025 filings. Current DB: Continental Strategy 2025 = **$26.0M / 349
   filings** (claim: $20.8M / 318 — reproduces exactly at a 2026-01-19/20 posting cutoff);
   Tariff FY2025 = **$218.9M** (claim: $206.5M). The claims *understate* both trends.
3. **LOC Nation field label:** the exact $20,000,000 per quarter (Q2/Q3/Q4 2025 — confirmed)
   sits in the **income** field (registrant fee), not `expenses`; the pipeline's
   `coalesce(expenses, income)` convention makes the amounts correct as stated.

Corroboration found beyond the claims: SAP America's anomalous Q2-2022 $130.09M filing
(`8753c1ce-20ee-403f-8fe5-de2264487a9a`) was **amended one day later to $640K**
(2A, posted 2022-07-21) — strong evidence of a data-entry error, supporting the report's
single-quarter-artifact reading.

| Claim | Verdict | Verifier numbers | Note |
|---|---|---|---|
| C1 Anthropic $0→$3.12M | verified | 2022: $0; 2025 self-filed $3.12M (exact) | first-appearance hedge (2023) |
| C2 OpenAI $0→$2.99M | verified | 2022: $0; 2025 self-filed $2.99M (exact) | first-appearance hedge (2023) |
| C3 a16z $0→$3.48M | verified | 2022: $0; 2025 self-filed $3.53M (Δ1.4%) | self-filed since 2023 |
| C4 Tariff surge, no taper | verified | FY22 $68.2M → FY25 $218.9M (+221%); Q1 avg $17.1M → $42.3M → $60.3M | Δ≤6%; 2026 climb confirmed |
| C5 SAP single-quarter artifact | verified | Q2-2022 raw $130.09M; 2025 $3.62M | next-day amendment to $640K strengthens |
| C6 Continental Strategy growth | verified | 2022 $0.40M/11 → 2025 $26.03M/349 | stale-snapshot caveat; claim understates |
| C7 LOC Nation $20M ×3 | verified | Q2=Q3=Q4 2025 exactly $20,000,000 | field is income, not expenses |
| C8 Business Roundtable name mismatch | verified | mismatch in 100% of self-filed filings, 2022–2026 | — |

Spot-checked records: `8753c1ce-20ee-403f-8fe5-de2264487a9a` (SAP Q2-2022),
`f77a4908-5b4f-41d6-a9c7-acc85dee6946` (LOC Nation Q4-2025),
`ba2fc44f-6b7a-42c0-abc8-a833ef824d69` (Anthropic Q3-2025),
`86980775-2940-4b00-a39d-c6624db22a0f` (Business Roundtable Q1-2022).

Lock decision: pending human sign-off in `DECISIONS.md` (per protocol step 6).
