---
name: lobbying-quarterly-filings
description: Load, clean, and analyze Senate LDA quarterly lobbying disclosures from the local data/senate/ corpus (no API key, no network) -- deduped spend totals, top-spenders-over-time, top-spenders-by-ALI-issue-code, and the fact-checkable raw filings behind any of those rankings.
---

# Lobbying quarterly filings

Adapts the `lobbyR` R package (github.com/Lobbying-DisclosuRe/lobbyr, built against the live
`lda.gov` API) to run entirely against the pre-downloaded corpus in `data/senate/`. Scope is
deliberately limited to the **Senate quarterly activity filings** (`data/senate/*/filings/`)
-- not House data, not the LD-203 contribution reports, not registrations-only filings.

Everything here is R. Rscript is available on this machine with all required packages
(`dplyr`, `tidyr`, `stringr`, `jsonlite`, `purrr`, `tibble`) already installed -- no
`install.packages()` or network access needed to run any of this.

## When to use this

- "How much did X spend lobbying, and did that change quarter to quarter?"
- "Who are the top lobbying spenders in [issue area] in [year/quarter]?"
- Any question about `data/senate/*/filings/` that isn't about registrations-only or the
  LD-203 contribution reports (out of scope here -- this skill is quarterly activity
  filings specifically).

## Workflow

1. **Load.** Call `get_local_senate_filings(years, ...)`. Accepts a vector of years (unlike
   the live API, which is one year per call) and supports the same filter vocabulary
   `get_filings()` does (client/registrant name, filing_period, date range, amount range).
   Prints a disclaimer message about double-counting on load (`ignore_disclaimer = TRUE`
   suppresses it once you've internalized it).

2. **Clean.** Pipe the result through `flag_dupes()` then `flag_client_registrant_conflict()`
   (`scripts/lobbyr_clean.R`, vendored verbatim from lobbyR). **Both default to actually
   removing** duplicate/conflicting rows, not just flagging them -- this is deliberate, not an
   oversight. If you need to audit what got dropped, call with `attempt_cleaning = FALSE` /
   `clean_doublecounts = FALSE` to see the flagged-but-uncleaned frame first.

   ```r
   cleaned <- get_local_senate_filings(years = 2022:2026, ignore_disclaimer = TRUE) |>
     flag_dupes() |>
     flag_client_registrant_conflict()
   ```

3. **Analyze**, using the cleaned frame:
   - `top_spenders_over_time(cleaned, entity_col = "client.name", metric = "expenses", n = 20)`
     -- ranks entities by total spend and returns quarter-by-quarter totals with rank and
     change vs. the prior quarter, in both wide (entity x quarter) and long formats.
   - `top_spenders_by_issue(cleaned, ali_codes = "TAX", entity_col = "client.name", metric = "expenses", n = 20)`
     -- same ranking, narrowed to one or more 3-letter ALI issue codes (`list_ali_codes()`
     to look one up; `data/senate/constants/lobbying_activity_issues.json` has the full
     table). **Requires loading with `tidy_result = FALSE`** -- the default `tidy_result =
     TRUE` strips the wide issue-topic columns this needs entirely, and
     `filter_by_ali_code()`/`top_spenders_by_issue()` will error clearly if you forget.
     `issue_joiner = "and"` requires all requested codes on the same filing; default `"or"`
     matches any of them. Note the ranking metric is each entity's **total filing spend for
     filings that touch the requested issue(s)**, not a per-issue dollar breakdown -- LDA
     filings report one income/expenses figure for the whole filing, not itemized by issue,
     so a multi-issue lobbyist's full filing amount counts toward every issue it touches.

     ```r
     df <- get_local_senate_filings(years = 2022:2026, tidy_result = FALSE, ignore_disclaimer = TRUE) |>
       flag_dupes() |>
       flag_client_registrant_conflict()

     top_spenders_by_issue(df, ali_codes = "TAX", n = 20)
     top_spenders_by_issue(df, ali_codes = c("TAX", "BUD"), issue_joiner = "or", n = 10)
     ```

   - **Fact-checking.** A ranking is a sum -- it doesn't show which filings produced it.
     `top_spenders_by_issue()`'s return value includes a `raw_filings` element (one row per
     underlying filing, not aggregated) alongside `long`/`wide`/`entity_totals`, so every
     number traces back to specific, linkable filings. `get_raw_filings_by_issue(df,
     ali_codes)` gets you the same thing standalone, without computing a ranking at all.
     Both return `filing_document_url` -- the link to the filing as filed -- plus every
     column a journalist needs to verify a figure by hand: `registrant.name`, `client.name`,
     `filing_type_display`, `income`, `expenses`, `filing_year`, `dt_posted`,
     `registrant.description`, `client.general_description`, `filing_type`, `filing_period`,
     and the flattened issue-topic text itself. See Example 6.

4. Two raw-data columns are surfaced on the loader's output but deliberately **not
   classified** here -- that's future analysis work, not this skill: `covered_positions`
   (text of every lobbyist's `covered_position` field on the filing -- revolving-door mining
   starts here) and `foreign_entities_flag` / `foreign_entity_names` (whether/who the filing
   lists as a foreign entity).

## Examples

Every example below was actually run against the real 2026 Q1 corpus, not invented -- the
printed output is copy-pasted from the console, so you can sanity-check your own run against
it. Start by sourcing everything once:

```r
source("skills/lobbying-quarterly-filings/scripts/local_senate_filings.R")
source("skills/lobbying-quarterly-filings/scripts/lobbyr_clean.R")
source("skills/lobbying-quarterly-filings/scripts/top_spenders_over_time.R")
source("skills/lobbying-quarterly-filings/scripts/top_spenders_by_issue.R")

df <- get_local_senate_filings(years = 2026, tidy_result = FALSE, ignore_disclaimer = TRUE)
cleaned <- df |> flag_dupes() |> flag_client_registrant_conflict()
```

(`tidy_result = FALSE` here because a couple of the examples below need the wide issue-topic
columns; drop it if you only want `top_spenders_over_time()`, which works on either shape.)

### 1. Look up a code before using it

You rarely remember 3-letter ALI codes offhand -- `list_ali_codes()` returns the full table,
and it's a normal data frame so you can search it like any other:

```r
codes <- list_ali_codes()
codes[grepl("energy|environ", codes$name, ignore.case = TRUE), ]
```
```
# A tibble: 2 × 2
  code  name
  <chr> <chr>
1 ENG   Energy/Nuclear
2 ENV   Environment/Superfund
```

### 2. Top spenders on a single issue

```r
top_spenders_by_issue(cleaned, ali_codes = "TAX", n = 5)$entity_totals
```
```
# A tibble: 5 × 2
  entity                                               grand_total
1 CHAMBER OF COMMERCE OF THE U.S.A.                        19750000
2 NATIONAL ASSOCIATION OF REALTORS                         15460000
3 GENERAL MOTORS COMPANY                                   11380000
4 AMERICAN MEDICAL ASSOCIATION                              7970000
5 BUSINESS ROUNDTABLE INC                                   7590000
```

### 3. Multiple issues at once (`OR` vs `AND`)

```r
# matches filings touching TAX or BUD (Budget/Appropriations)
top_spenders_by_issue(cleaned, ali_codes = c("TAX", "BUD"), issue_joiner = "or", n = 5)$entity_totals
```
```
# A tibble: 5 × 2
  entity                                               grand_total
1 CHAMBER OF COMMERCE OF THE U.S.A.                        19750000
2 NATIONAL ASSOCIATION OF REALTORS                         15460000
3 PHARMACEUTICAL RESEARCH AND MANUFACTURERS OF AMERICA     12210000
4 GENERAL MOTORS COMPANY                                   11380000
5 AMERICAN MEDICAL ASSOCIATION                              7970000
```
Swap `issue_joiner = "and"` to require *both* TAX and BUD on the same filing -- a much smaller,
more targeted set.

### 4. Who's getting paid, not just who's paying

Switch `entity_col` from `"client.name"` (default -- who's paying for lobbying) to
`"registrant.name"` (who's being hired to do it):

```r
top_spenders_by_issue(cleaned, ali_codes = "TAX", entity_col = "registrant.name", n = 5)$entity_totals
```
```
# A tibble: 5 × 2
  entity                            grand_total
1 CHAMBER OF COMMERCE OF THE U.S.A.     19750000
2 NATIONAL ASSOCIATION OF REALTORS      15460000
3 GENERAL MOTORS COMPANY                11380000
4 AMERICAN MEDICAL ASSOCIATION           7970000
5 THE BUSINESS ROUNDTABLE, INC.          7590000
```
(These five all lobby in-house -- registrant and client are the same organization -- which is
why the ranking looks identical to Example 2. Try it on an issue area with more outside-firm
activity and the two rankings will diverge.)

### 5. Quarter-by-quarter view for one issue

`$wide` gives you an entity x quarter matrix instead of a single grand total -- more useful
once you've loaded more than one year (`years = 2022:2026`) and want to see a trend, not just
a single-quarter snapshot:

```r
top_spenders_by_issue(cleaned, ali_codes = "HCR", n = 3)$wide
```
```
# A tibble: 3 × 2
  entity                                               `2026-Q1`
1 AMERICAN MEDICAL ASSOCIATION                            7970000
2 CHAMBER OF COMMERCE OF THE U.S.A.                      19750000
3 PHARMACEUTICAL RESEARCH AND MANUFACTURERS OF AMERICA   12210000
```
Load `years = 2022:2026` instead of just `2026` to see this fill out with one column per
quarter and the `change_abs`/`change_pct`/`rank_in_quarter` columns in `$long` start telling
you something (a single quarter has nothing to compare against).

### 6. Fact-check a number in the ranking

`entity_totals` says the Chamber of Commerce leads TAX spending at $19,750,000. Don't take
that on faith -- `raw_filings` is right there in the same result, filter it to the entity in
question, and every dollar traces to an actual filing you can open:

```r
res <- top_spenders_by_issue(cleaned, ali_codes = "TAX", n = 5)

top1 <- res$entity_totals$entity[1]
dplyr::filter(res$raw_filings, client.name == top1) |>
  dplyr::select(registrant.name, filing_type_display, income, expenses, dt_posted, filing_document_url)
```
```
                    registrant.name  filing_type_display income    expenses  dt_posted
1 CHAMBER OF COMMERCE OF THE U.S.A. 1st Quarter - Report     NA 19750000.00 2026-04-20
                                                                       filing_document_url
1 https://lda.senate.gov/filings/public/filing/c68f37ff-d80d-4b53-8835-08bdbf54a5b2/print/
```
One filing, `expenses` of exactly $19,750,000 -- matches `entity_totals` exactly, and the
`filing_document_url` opens the filing as filed with the Senate so you can check it against
the primary source. (Summed across however many filings an entity has, `raw_filings`'
`expenses`/`income` always reconciles to `entity_totals`' `grand_total` -- verified directly,
not assumed.)

Don't need a ranking at all, just the underlying filings for an issue? Skip straight to
`get_raw_filings_by_issue(cleaned, ali_codes = "TAX")` -- same columns, no aggregation step.

## Dashboard

`dashboard_app.R` (repo root) is a Shiny app that puts this skill's functions behind a UI --
launch with `Rscript -e 'shiny::runApp(shinyAppFile("dashboard_app.R"))'`. Two of its tabs are
this skill:

- **Search Filings** -- a form over `get_local_senate_filings()` (issues/issue_joiner, years,
  client/registrant name, filing period, date range, amount range, `tidy_result`), plus radio
  buttons that call `flag_dupes()`/`flag_client_registrant_conflict()` on the result and a
  "Quick math" sum-totals helper. No API key section -- unlike `app.R` (the live-API
  reference this dashboard is based on), there's nothing to authenticate.
- **Top Spenders by Issue** -- a UI over `top_spenders_by_issue()`: `ali_codes` is a
  multi-select dropdown built from `list_ali_codes()`; its OR/AND control is named
  `ali_issue_joiner` specifically because Search Filings already has an `issue_joiner`
  input and Shiny input IDs are global across the whole app, not scoped per tab (this tab
  also duplicates every Search Filings filter under fresh `ts_`-prefixed IDs, so an ALI code
  can be combined with a registrant name, date range, etc. the same way Search Filings
  combines filters). A checkbox (`ts_factcheck`, off by default, with in-UI documentation of
  exactly what it does) reveals every raw filing matching the current search -- not just the
  top N in the ranking -- with `FACT_CHECK_COLS` plus one `processed_<issue display name>`
  column per selected ALI code, so a journalist can read the filing's own text for that issue
  without leaving the dashboard.

## Files

- `scripts/lobbyr_clean.R` -- vendored `flag_dupes()` + `flag_client_registrant_conflict()`,
  plus a project-local `normalize_entity_name()` used by the latter. Vendored (not
  `remotes::install_github()`'d at run time) so this skill has zero network dependency when
  re-run. **One deliberate departure from upstream**: `flag_client_registrant_conflict()`'s
  entity matching now strips legal-entity suffixes/filler words (THE/INC/LLC/CORP/etc.), not
  just punctuation and case -- see `references/data_quality_notes.md`'s "Entity name-variant
  matching" section for the root-caused bug this fixes (verified against the real corpus: the
  original normalization caught 0 of the ~244 Business Roundtable outside-firm filings that
  should have been recognized as double-counting its own self-filed report, across all 5
  years on file; re-running the fixed function against the full 317k-filing corpus caught
  13,923 additional double-counting rows corpus-wide that the original logic silently missed).
- `scripts/local_senate_filings.R` -- `get_local_senate_filings()`.
- `scripts/top_spenders_over_time.R` -- `top_spenders_over_time()`.
- `scripts/top_spenders_by_issue.R` -- `list_ali_codes()`, `filter_by_ali_code()`,
  `top_spenders_by_issue()`, `get_raw_filings_by_issue()` -- the same ranking as above,
  narrowed to one or more 3-letter ALI issue codes, plus the fact-checkable raw filings
  behind it (`FACT_CHECK_COLS` -- `registrant.name`, `client.name`, `filing_type_display`,
  `income`, `expenses`, `filing_year`, `dt_posted`, `filing_document_url`,
  `registrant.description`, `client.general_description`, `filing_type`, `filing_period`).
  Requires the `tidy_result = FALSE` loader output (see Workflow step 3).
- `references/schema.md` -- column dictionary for the loader's output.
- `references/data_quality_notes.md` -- lobbyR's double-counting disclaimer, filing_type
  code table, and corpus-specific gotchas.

## Performance note

`jsonlite::fromJSON()` on a full year of Senate filings (~100k+ deeply nested records, e.g.
2025) takes **4-6 minutes** -- benchmarked directly, and confirmed this is the parse itself,
not the `flatten=TRUE` option (flatten was actually *faster* than parsing without it: 230s
vs 327s on the 2025 file). `get_local_senate_filings()` caches each year's raw parsed frame
as `.rds` under `.cache/` (gitignored), so the first call per year pays this cost and
subsequent calls are near-instant. Cache invalidates automatically if the source JSON is
newer than the cache entry; delete `skills/lobbying-quarterly-filings/.cache/` to force a
full re-parse.

