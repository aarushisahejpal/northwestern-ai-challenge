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

## Known gaps (from `data_manual.md`, still true for the local corpus)

- Many filings lack income/expenses/state data -- the gaps are themselves worth noting in
  any downstream story, not just filtered out silently.
- The corpus is self-reported, public-record data expected to contain real errors --
  treat any single-source finding as a lead, not a conclusion, and check the primary
  document (`filing_document_url`) before publishing a claim built on it.
