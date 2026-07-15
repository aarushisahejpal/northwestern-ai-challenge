# Adapts the user's own reference function (new_process_lobbying_data(df, start_col, end_col))
# for pulling a single-issue-area slice out of the wide Senate filings frame ahead of LLM
# classification. Generalized from column INDEX to column NAME -- the pivoted issue-code
# columns' exact positions shift depending on which years/quarters were loaded and which
# carry-through columns the loader adds, so indices like [66:130] aren't stable across calls;
# names (e.g. "Taxation/Internal Revenue Code") are.
#
# Also folds in the time filters (years/filing_period/date range) so issue selection and
# time-window selection happen in one call, and supports selecting more than one issue area
# at once (issue_joiner = "or"/"and", mirroring get_local_senate_filings()'s own convention).

#' Select a Senate filings subset by issue area (and optionally time window)
#'
#' @param years Numeric vector of filing years to load, passed to get_local_senate_filings().
#' @param issue_names Character vector of one or more issue-code display names, e.g.
#'   "Taxation/Internal Revenue Code" (see data/senate/constants/lobbying_activity_issues.json
#'   for the full list of valid display names).
#' @param issue_joiner "or" (default, any selected issue matches) or "and" (all selected issues
#'   must be present on the filing).
#' @param filing_period,starting_date,ending_date Optional time filters, passed straight
#'   through to get_local_senate_filings().
#' @param data_root Path to the senate data directory. Default "data/senate".
#'
#' @returns A data frame: the core filing metadata columns plus one `processed_<issue name>`
#'   text column per requested issue (list-cell values flattened to a single "; "-joined
#'   string), filtered to rows where at least one (or all, if issue_joiner = "and") of the
#'   requested issues has non-empty text.
prepare_issue_subset <- function(years,
                                  issue_names,
                                  issue_joiner = "or",
                                  filing_period = NULL,
                                  starting_date = NULL,
                                  ending_date = NULL,
                                  data_root = "data/senate") {
  df <- get_local_senate_filings(
    years = years,
    filing_period = filing_period,
    starting_date = starting_date,
    ending_date = ending_date,
    data_root = data_root,
    tidy_result = FALSE,
    ignore_disclaimer = TRUE
  )

  meta_cols <- c(
    "registrant.name", "client.name", "filing_type_display", "income", "expenses",
    "filing_year", "dt_posted", "filing_document_url", "registrant.description",
    "client.general_description", "filing_type", "filing_period"
  )
  issue_cols <- intersect(issue_names, names(df))
  missing_issues <- setdiff(issue_names, names(df))
  if (length(missing_issues) > 0) {
    warning("Issue name(s) not found in this data (no filings tagged, or typo?): ",
            paste(missing_issues, collapse = ", "))
  }
  if (length(issue_cols) == 0) {
    stop("None of the requested issue_names are present as columns in this data.")
  }

  flattened <- df |>
    dplyr::select(dplyr::any_of(c(meta_cols, issue_cols))) |>
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
