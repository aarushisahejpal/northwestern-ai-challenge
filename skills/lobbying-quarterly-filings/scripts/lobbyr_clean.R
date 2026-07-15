# Vendored from https://github.com/Lobbying-DisclosuRe/lobbyr (flag_dupes.R,
# flag_client_registrant_conflict.R). Both functions operate purely on the tidy data
# frame shape get_filings()/get_local_senate_filings() produce (registrant.name,
# client.name, filing_type, filing_year, filing_period, income, expenses,
# dt_posted) -- no API calls inside either one.
#
# See references/data_quality_notes.md for the double-counting rationale.
#
# ONE DELIBERATE DEPARTURE FROM UPSTREAM: flag_client_registrant_conflict()'s entity-match
# normalization (see normalize_entity_name() below). Root-caused against the real corpus,
# not assumed -- see references/data_quality_notes.md's "Entity name-variant matching" section
# for the full trace (Business Roundtable's self-filed row has registrant.name = "THE
# BUSINESS ROUNDTABLE, INC." but client.name = "BUSINESS ROUNDTABLE INC" -- not identical even
# within its own filing, in any of 5 years on file -- so the self-lobbying check never fired
# for it under the original punctuation/case-only normalization).

#' Normalize an entity name for cross-filing matching
#'
#' Registrants and clients in this corpus refer to the same real organization with
#' inconsistent legal-suffix and filler-word usage across filings and even, in some cases,
#' within a single self-filed row's own registrant.name vs. client.name fields (verified:
#' "THE BUSINESS ROUNDTABLE, INC." vs "BUSINESS ROUNDTABLE INC", same registrant.id/client.id,
#' every year 2022-2026). Stripping punctuation and case (the original normalization) isn't
#' enough -- this also drops a small, deliberately conservative list of legal-entity
#' suffixes/filler words as whole tokens (not substrings), so it can't accidentally truncate a
#' real word (e.g. it won't touch "COALITION" or "GROUP" or "ASSOCIATION", which are often
#' load-bearing parts of an org's actual name, not filler).
#'
#' Validated two ways against the full local corpus (317k filings) before adoption: (1) the
#' known Business Roundtable spellings ("BUSINESS ROUNDTABLE", "THE BUSINESS ROUNDTABLE",
#' "THE BUSINESS ROUNDTABLE, INC.", "BUSINESS ROUNDTABLE (THE)", "BUSINESS ROUNDTABLE INC")
#' all collapse to one key, while the four genuinely distinct regional Business Roundtables
#' (Gulf South/Ohio/Colorado/American Turkish) correctly do not; (2) applied to all 30,528
#' distinct client.name strings corpus-wide (1,880 groups, 4,017 raw names collapse), every
#' one of the highest-false-merge-risk groups (shortest resulting normalized name -- "2U",
#' "3M", "ATT", "GAP", "ARM", "FMC", "IAC", etc.) was hand-checked and found to be a genuine
#' same-entity suffix/punctuation variant, not an accidental merge of two unrelated orgs.
#'
#' Tokenizes on whitespace rather than using a `\\b`-anchored regex deliberately -- this
#' project's own tooling hit a real bug where an inline `Rscript -e` invocation silently
#' mangled `"\\b"` into a literal backspace character before R ever parsed it (confirmed via
#' `nchar("\\btest")` returning a value inconsistent with two literal characters), which made
#' every `\\b`-based match silently match nothing. Token-splitting sidesteps that class of bug
#' entirely regardless of which execution path calls this function.
#'
#' @param x Character vector of registrant or client names.
#' @returns Character vector, uppercased, punctuation removed, common legal-suffix/filler
#'   tokens dropped, whitespace squished.
normalize_entity_name <- function(x) {
  stopwords <- c("THE", "INC", "INCORPORATED", "LLC", "LLP", "LP", "LTD", "LIMITED",
                 "CORP", "CORPORATION", "CO", "COMPANY", "PLLC", "PC", "PLC")
  x <- stringr::str_to_upper(x)
  x <- stringr::str_remove_all(x, "[[:punct:]]")
  tokens <- stringr::str_split(x, "\\s+")
  vapply(tokens, function(t) {
    t <- t[!(t %in% stopwords) & nzchar(t)]
    paste(t, collapse = " ")
  }, character(1))
}

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
#' Entity matching uses `normalize_entity_name()` (strips legal-entity suffixes/filler
#' words, not just punctuation/case -- see that function's doc for why: verified against
#' real filings, e.g. Business Roundtable's own self-filed row has registrant.name "THE
#' BUSINESS ROUNDTABLE, INC." vs. client.name "BUSINESS ROUNDTABLE INC", which the original
#' punctuation/case-only normalization never recognized as the same entity, in any of the 5
#' years on file).
#'
#' @param dataframe_that_i_determine A data frame of filings (e.g. from get_filings() or get_local_senate_filings()).
#' @param flag_conflict Logical. If TRUE (default), flags filings where an entity appears as both registrant and client elsewhere.
#' @param clean_doublecounts Logical. If TRUE (default), removes filings likely to cause double-counting.
#' @returns A data frame with a `flag` column and, optionally, conflicting rows removed.
flag_client_registrant_conflict <- function(dataframe_that_i_determine, flag_conflict = TRUE, clean_doublecounts = TRUE) {
  if (flag_conflict) {
    dataframe_that_i_determine <- dataframe_that_i_determine |>
      dplyr::mutate(
        registrant_clean = normalize_entity_name(registrant.name),
        client_clean = normalize_entity_name(client.name)
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
