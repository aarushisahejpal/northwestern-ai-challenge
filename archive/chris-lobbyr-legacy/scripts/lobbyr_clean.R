# Vendored from https://github.com/Lobbying-DisclosuRe/lobbyr (flag_dupes.R,
# flag_client_registrant_conflict.R). Logic is unchanged from upstream; vendored
# here (rather than remotes::install_github() at run time) so this skill has no
# network dependency when an evaluator re-runs it. Both functions operate purely
# on the tidy data frame shape get_filings()/get_local_senate_filings() produce
# (registrant.name, client.name, filing_type, filing_year, filing_period, income,
# expenses, dt_posted) -- no API calls inside either one.
#
# See references/data_quality_notes.md for the double-counting rationale.

#' Flag and Clean Duplicate or Dubious Lobbying Filings
#'
#' @param cleaned_dataframe_from_previous_function A data frame of filings (e.g. from get_filings() or get_local_senate_filings()).
#' @param find_duplicates Logical. If TRUE (default), flags dubious filings using regex/heuristics.
#' @param attempt_cleaning Logical. If TRUE (default), removes all but the latest filing per registrant-client-quarter group.
#' @returns A data frame with diagnostic columns added and (optionally) duplicates removed.
flag_dupes <- function(cleaned_dataframe_from_previous_function, find_duplicates = TRUE, attempt_cleaning = TRUE) {
  if (find_duplicates) {
    dupes_flagged <- cleaned_dataframe_from_previous_function |>
      dplyr::mutate(
        registration_or_termination = stringr::str_detect(filing_type, stringr::regex("RR$|T$", ignore_case = TRUE)),
        quarter_number = stringr::str_extract(filing_type, "\\d+") |> as.integer(),
        is_amendment = stringr::str_detect(filing_type, "\\d+A$")
      ) |>
      dplyr::group_by(registrant.name, client.name, filing_year, quarter_number) |>
      dplyr::mutate(
        has_quarter = any(!is_amendment & !is.na(quarter_number)),
        has_amendment = any(is_amendment),
        registration_termination = any(registration_or_termination),
        is_duplicate = (duplicated(income) | duplicated(income, fromLast = TRUE) | duplicated(expenses) | duplicated(expenses, fromLast = TRUE)),
        checkme = dplyr::if_else(
          has_quarter & has_amendment, "CHECK",
          dplyr::if_else(!has_quarter & !has_amendment & !is_amendment, "CHECK",
                         dplyr::if_else(registration_termination | is_amendment | is_duplicate, "CHECK", "PASS CHECK"))
        )
      ) |>
      dplyr::ungroup()
  } else {
    dupes_flagged <- cleaned_dataframe_from_previous_function
  }
  clean_attempt <- function(dataframe_with_flagged_dupes) {
    dataframe_with_flagged_dupes |>
      dplyr::filter(!registration_or_termination) |>
      dplyr::mutate(dt_posted = as.POSIXct(dt_posted)) |>
      dplyr::group_by(registrant.name, client.name, filing_year, filing_period) |>
      dplyr::arrange(dplyr::desc(dt_posted)) |>
      dplyr::slice_tail(n = 1) |>
      dplyr::ungroup()
  }
  if (attempt_cleaning) {
    cleaned_and_flagged_dataframe <- clean_attempt(dupes_flagged)
  } else {
    cleaned_and_flagged_dataframe <- dupes_flagged
  }
  message("This function either removed or identified lobbying filings that, if left in, could lead to doublecounting of spending on lobbying. It is not perfect. Please see documentation on tips for fact-checking these by hand.")
  return(cleaned_and_flagged_dataframe)
}

#' Identify and Resolve Potential Double-Counting of Client/Registrant
#'
#' @param dataframe_that_i_determine A data frame of filings (e.g. from get_filings() or get_local_senate_filings()).
#' @param flag_conflict Logical. If TRUE (default), flags filings where an entity appears as both registrant and client elsewhere.
#' @param clean_doublecounts Logical. If TRUE (default), removes filings likely to cause double-counting.
#' @returns A data frame with a `flag` column and, optionally, conflicting rows removed.
flag_client_registrant_conflict <- function(dataframe_that_i_determine, flag_conflict = TRUE, clean_doublecounts = TRUE) {
  if (flag_conflict) {
    dataframe_that_i_determine <- dataframe_that_i_determine |>
      dplyr::mutate(
        registrant_clean = stringr::str_remove_all(
          stringr::str_squish(stringr::str_to_lower(stringr::str_remove_all(registrant.name, "[[:punct:]]"))),
          "\\s"
        ),
        client_clean = stringr::str_remove_all(
          stringr::str_squish(stringr::str_to_lower(stringr::str_remove_all(client.name, "[[:punct:]]"))),
          "\\s"
        )
      )
    self_lobbying_entities <- dataframe_that_i_determine |>
      dplyr::filter(registrant_clean == client_clean) |>
      dplyr::distinct(entity = registrant_clean)

    flagged_cases <- dataframe_that_i_determine |>
      dplyr::mutate(
        flag = dplyr::case_when(
          registrant_clean == client_clean ~ "Report of all entity's spending",
          client_clean %in% self_lobbying_entities$entity ~ "Likely part of separate entity's report",
          TRUE ~ "No entity's report detected"
        )
      )
  } else {
    flagged_cases <- dataframe_that_i_determine
  }
  remove_client_registrant_conflict <- function(dataframe_i_cleaned_above) {
    dataframe_i_cleaned_above |>
      dplyr::filter(flag != "Likely part of separate entity's report")
  }
  if (clean_doublecounts) {
    filtered_dataframe_with_flagged_conflict_col <- remove_client_registrant_conflict(flagged_cases)
  } else {
    filtered_dataframe_with_flagged_conflict_col <- flagged_cases
  }
  message("This function either removed or identified lobbying filings that, if left in, could lead to doublecounting of spending on lobbying. It is not perfect. Please see documentation on tips for fact-checking these by hand.")
  return(filtered_dataframe_with_flagged_conflict_col)
}
