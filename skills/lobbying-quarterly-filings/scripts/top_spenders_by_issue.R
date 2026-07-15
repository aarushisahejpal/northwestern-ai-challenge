# Narrows top_spenders_over_time() to a specific lobbying issue area, keyed by the
# 3-letter ALI code (data/senate/constants/lobbying_activity_issues.json) rather than
# the issue's full display name or a fragile column-index range.
#
# Adapts the pattern from the user's own new_process_lobbying_data(df, start_col, end_col)
# (select metadata cols + an issue-column range, filter to non-empty, flatten list-cells to
# strings) -- generalized from column INDEX to code LOOKUP BY NAME, since a wide frame's
# exact column positions shift depending on which years are loaded (get_local_senate_filings()
# only pivots the issue columns actually present in the requested data).
#
# Requires the untidy loader output: get_local_senate_filings(..., tidy_result = FALSE).
# The default tidy_result = TRUE strips the wide issue-topic columns entirely, since they're
# not part of get_filings()'s tidy column whitelist.

# Core fact-checkable columns for a single filing -- enough for a journalist to verify a
# number against the original source document without having to reload the whole wide
# frame. `filing_document_url` is the key one: it links straight to the filing as filed.
FACT_CHECK_COLS <- c(
  "registrant.name", "client.name", "filing_type_display", "income", "expenses",
  "filing_year", "dt_posted", "filing_document_url", "registrant.description",
  "client.general_description", "filing_type", "filing_period"
)

#' List the 3-letter ALI issue codes and their display names
#'
#' @param issue_lookup_path Path to the code/name lookup. Default
#'   "data/senate/constants/lobbying_activity_issues.json".
#' @returns A data frame with `code` and `name` columns, e.g. code "TAX", name
#'   "Taxation/Internal Revenue Code" -- look up a code here before calling
#'   filter_by_ali_code()/top_spenders_by_issue().
list_ali_codes <- function(issue_lookup_path = "data/senate/constants/lobbying_activity_issues.json") {
  codes <- jsonlite::fromJSON(issue_lookup_path)
  tibble::tibble(code = codes$value, name = codes$name)
}

#' Filter a wide (tidy_result = FALSE) filings frame to one or more ALI issue codes
#'
#' @param df A data frame from get_local_senate_filings(..., tidy_result = FALSE)
#'   (optionally already cleaned via flag_dupes()/flag_client_registrant_conflict()).
#' @param ali_codes Character vector of one or more 3-letter ALI codes, e.g. "TAX" or
#'   c("TAX", "BUD"). Case-insensitive. See list_ali_codes() for the full list.
#' @param issue_joiner "or" (default, matches if ANY requested code is present on the
#'   filing) or "and" (all requested codes must be present).
#' @param issue_lookup_path Path to the code/name lookup, same default as list_ali_codes().
#'
#' @returns `df` filtered to rows where the requested issue code(s) have real content,
#'   with `processed_<issue display name>` column(s) added (list-cell values flattened to a
#'   single "; "-joined string) -- all other columns are left untouched, unlike the
#'   reference implementation this adapts, which narrows to a fixed metadata subset. Kept
#'   here because downstream top_spenders_over_time()/flag_dupes()/flag_client_registrant_conflict()
#'   need columns beyond that fixed list.
filter_by_ali_code <- function(df, ali_codes, issue_joiner = "or",
                                issue_lookup_path = "data/senate/constants/lobbying_activity_issues.json") {
  codes <- jsonlite::fromJSON(issue_lookup_path)
  lookup <- stats::setNames(codes$name, toupper(codes$value))

  ali_codes <- toupper(ali_codes)
  unknown <- setdiff(ali_codes, names(lookup))
  if (length(unknown) > 0) {
    stop(
      "Unknown ALI code(s): ", paste(unknown, collapse = ", "),
      ". Call list_ali_codes() to see valid codes."
    )
  }

  issue_cols <- intersect(unname(lookup[ali_codes]), names(df))
  if (length(issue_cols) == 0) {
    stop(
      "None of the requested ALI code(s) are present as columns in this data -- ",
      "did you load with get_local_senate_filings(..., tidy_result = FALSE)?"
    )
  }

  flattened <- df |>
    dplyr::mutate(dplyr::across(
      dplyr::all_of(issue_cols),
      ~ purrr::map_chr(.x, ~ paste(unlist(.x), collapse = "; ")),
      .names = "processed_{.col}"
    ))

  processed_cols <- paste0("processed_", issue_cols)
  match_matrix <- sapply(processed_cols, function(col) nzchar(flattened[[col]]))
  if (is.null(dim(match_matrix))) match_matrix <- matrix(match_matrix, ncol = length(processed_cols))
  keep <- if (identical(issue_joiner, "and")) apply(match_matrix, 1, all) else apply(match_matrix, 1, any)

  flattened[keep, ]
}

#' Get the individual raw filings behind a specific ALI issue area, for fact-checking
#'
#' A ranking like `top_spenders_over_time()`'s `entity_totals` is a sum -- it doesn't let
#' you see which filings, on which dates, produced that number. This returns the actual
#' filing-level rows instead: one row per filing, narrowed to the columns a journalist
#' needs to verify a number by hand (`filing_document_url` links to the filing as filed),
#' plus the flattened issue-topic text so you can see, in the entity's own words, what the
#' filing said it was lobbying on.
#'
#' @inheritParams filter_by_ali_code
#' @returns A data frame, one row per filing matching the requested issue code(s), columns
#'   `FACT_CHECK_COLS` plus `processed_<issue display name>` for each requested code. Not
#'   aggregated or deduplicated beyond whatever cleaning you already did to `df` -- every
#'   matching filing is here, not just the top spenders.
get_raw_filings_by_issue <- function(df, ali_codes, issue_joiner = "or",
                                      issue_lookup_path = "data/senate/constants/lobbying_activity_issues.json") {
  subset_df <- filter_by_ali_code(df, ali_codes = ali_codes, issue_joiner = issue_joiner,
                                   issue_lookup_path = issue_lookup_path)
  processed_cols <- grep("^processed_", names(subset_df), value = TRUE)
  subset_df |> dplyr::select(dplyr::any_of(c(FACT_CHECK_COLS, processed_cols)))
}

#' Rank top spenders within a specific ALI issue area
#'
#' @param df A data frame from get_local_senate_filings(..., tidy_result = FALSE),
#'   ideally already cleaned via flag_dupes()/flag_client_registrant_conflict().
#' @param ali_codes,issue_joiner,issue_lookup_path Passed through to filter_by_ali_code().
#' @param entity_col,metric,n Passed through to top_spenders_over_time().
#'
#' @returns A list with everything top_spenders_over_time() returns (`long`, `wide`,
#'   `entity_totals`) computed only over filings tagged with the requested issue code(s),
#'   **plus `raw_filings`** -- the same output as get_raw_filings_by_issue(), so every
#'   number in the ranking traces back to specific, linkable source filings. Fact-check one
#'   entity's ranking with `dplyr::filter(result$raw_filings, client.name == "...")`.
top_spenders_by_issue <- function(df, ali_codes, issue_joiner = "or",
                                   issue_lookup_path = "data/senate/constants/lobbying_activity_issues.json",
                                   entity_col = "client.name", metric = "expenses", n = 20) {
  subset_df <- filter_by_ali_code(df, ali_codes = ali_codes, issue_joiner = issue_joiner,
                                   issue_lookup_path = issue_lookup_path)
  agg <- top_spenders_over_time(subset_df, entity_col = entity_col, metric = metric, n = n)

  processed_cols <- grep("^processed_", names(subset_df), value = TRUE)
  raw_filings <- subset_df |> dplyr::select(dplyr::any_of(c(FACT_CHECK_COLS, processed_cols)))

  c(agg, list(raw_filings = raw_filings))
}
