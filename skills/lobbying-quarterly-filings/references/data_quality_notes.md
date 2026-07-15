# Data quality notes

## lobbyR's double-counting disclaimer (why `flag_dupes()`/`flag_client_registrant_conflict()` exist)

Carried over from `get_filings()`'s printed disclaimer, because it's still exactly the
guidance that applies to this local data:

- Ensure there is only one filing for a given registrant in each `filing_period` for each
  year to avoid double-counting spend. If, in the same quarter, an entity has a
  `'1st Quarter - Report'`, a `'1st Quarter - Termination'`, and a `'1st Quarter - Amendment'`,
  only one should count -- the latest is usually most accurate. `flag_dupes()` handles this
  by default (`attempt_cleaning = TRUE`).
- Registrations (`RR`) and terminations (`*T`) are separate from quarterly lobbying spend and
  must be excluded from yearly spending totals. `flag_dupes()` drops these.
- If an entity appears as a **registrant** in one filing and as a **client** in someone
  else's filing, don't sum both values -- use the registrant's own expenses figure.
  `flag_client_registrant_conflict()` handles this by default (`clean_doublecounts = TRUE`).
- **This skill's loader defaults to removing these rows, not just flagging them** (per this
  project's explicit preference) -- pass `attempt_cleaning = FALSE` / `clean_doublecounts = FALSE`
  if you want to audit what would be dropped before it's gone.
- Neither cleaning function is perfect. Fact-check anything load-bearing against the
  `filing_document_url`.

## Filing type codes

`data/senate/constants/filing_types.json` has the full table. The ones that matter for
quarterly analysis:

| Code | Meaning |
|---|---|
| `RR` | Registration (not a quarterly spend report -- excluded by `flag_dupes()`) |
| `Q1`/`Q2`/`Q3`/`Q4` | Quarterly activity report |
| `Q#Y` | Quarterly report, no lobbying activity that quarter |
| `#T` | Quarterly termination (excluded by `flag_dupes()`) |
| `#A` | Quarterly amendment |
| `MM` / `YY` | Mid-year / year-end reports (pre-dates the current quarterly cadence; `top_spenders_over_time()` drops these since it's a quarter-over-quarter tool) |

## Entity name-variant matching (why `flag_client_registrant_conflict()` was changed)

**The bug, root-caused against real filings, not assumed.** `flag_client_registrant_conflict()`
detects "self-lobbying" by checking whether a row's `registrant.name` and `client.name` are the
same entity (that row is then the entity's own report), then flags every *other* row where
some *different* registrant filed on behalf of that same client as
`"Likely part of separate entity's report"` (removed by default, since the client's own report
already covers that spend). The original normalization only stripped punctuation and case.
That's not enough: Business Roundtable's own self-filed row has `registrant.name` = "THE
BUSINESS ROUNDTABLE, INC." but `client.name` = "BUSINESS ROUNDTABLE INC" -- **not identical
even within its own single filing**, consistently across all 5 years on file (same
`registrant.id`/`client.id` every year, so it's the same real filer typing its name two
different ways on the same form, not a data-entry one-off). Because the two fields never
matched under punctuation/case-only cleaning, the self-lobbying check never fired for this
entity in *any* year, so none of its ~244 outside-firm filings across 22 registrants (Akin
Gump, Ballard Partners, CGCN Group, Invariant, Mehlman Consulting, PwC, and others) were ever
recognized as double-counting its own report.

**The fix**: `normalize_entity_name()` in `scripts/lobbyr_clean.R` additionally strips a fixed,
conservative list of legal-suffix/filler tokens (THE, INC, INCORPORATED, LLC, LLP, LP, LTD,
LIMITED, CORP, CORPORATION, CO, COMPANY, PLLC, PC, PLC) as whole words, not substrings --
deliberately *not* stripping words like GROUP/ASSOCIATION/COALITION, which are often a
load-bearing part of an org's real name rather than filler.

**Two alternatives were checked and rejected before landing on name-normalization:**

- `registrant.id`/`client.id` (the numeric IDs Senate LDA assigns) looked like it might be a
  cleaner, deterministic fix -- and it partly is, but only on the *registrant* side. Checked
  corpus-wide: 6,416 distinct `registrant.name` strings collapse to 6,383 distinct
  `registrant.id` values, and every one of the 66 sampled collisions (e.g. "BALLARD PARTNERS"
  and "BALLARD PARTNERS, LLC" sharing `registrant.id` 401104288) was a genuine rebrand/suffix
  variant, not a false merge. That's a solid fix for rolling up *one registrant's own* spend
  across its name history (e.g. Ballard Partners) -- but it's a different problem from the one
  above, and doesn't help `flag_client_registrant_conflict()` at all, which compares a
  registrant to a *client*, not a registrant to itself over time.
- `client.id` does **not** work as a per-entity key -- checked and found actively unreliable:
  Business Roundtable's ~244 flagged filings carry on the order of 15+ different `client.id`
  values (essentially no overlap), and corpus-wide, the count of distinct `client.id` values
  (35,174) *exceeds* the count of distinct `client.name` strings (30,528) -- the opposite
  pattern from the registrant side. `client.id` in this data appears to be scoped per
  client-registrant registration relationship, not per real-world entity, so using it as a
  merge key would under-merge, not over-merge.

**Validated before shipping, not just unit-tested against the one known example:** applied
`normalize_entity_name()` to all 30,528 distinct `client.name` strings in the full corpus
(1,880 groups, 4,017 raw names collapse) and hand-checked every group with the shortest
resulting normalized name (the highest false-merge risk -- "2U", "3M", "ATT", "GAP", "ARM",
"FMC", "IAC", etc.); all were genuine same-entity suffix/punctuation variants. Also confirmed
the four genuinely *distinct* regional Business Roundtables (Gulf South, Ohio, Colorado,
Arizona, American Turkish) do **not** collapse into the national one. Re-running the fixed
`flag_client_registrant_conflict()` against the full, already-`flag_dupes()`-cleaned 317,089-row
corpus caught 13,923 additional rows (~4.4%) as double-counting conflicts the original logic
had silently missed -- this bug was not unique to Business Roundtable, and any dollar total
computed before this fix should be treated as a modest overstatement.

## Known gaps (from `data_manual.md`, still true for the local corpus)

- Many filings lack income/expenses/state data -- the gaps are themselves worth noting in
  any downstream story, not just filtered out silently.
- The corpus is self-reported, public-record data expected to contain real errors --
  treat any single-source finding as a lead, not a conclusion, and check the primary
  document (`filing_document_url`) before publishing a claim built on it.
