# Drop-in local replacement for lobbyR::get_filings() that reads the pre-downloaded
# Senate LDA JSON in data/senate/{year}/filings/filings_{year}.json instead of
# calling the live lda.gov API. The local JSON is the same shape as the API's
# `results` array (verified against get_filings.R's httr2::resp_body_json(...,
# simplifyVector = TRUE, flatten = TRUE) call), so this loader reproduces the
# exact tidy output shape get_filings() returns -- flag_dupes() and
# flag_client_registrant_conflict() (scripts/lobbyr_clean.R) run on it unmodified.
#
# Unlike get_filings(), which is capped at one `year` per API call, `years` here
# accepts a vector so a single call can span the whole 2022-2026 Q1 corpus.

#' Load local Senate LDA quarterly filings
#'
#' @param years Numeric vector of filing years to load, e.g. 2022:2026.
#' @param data_root Path to the senate data directory. Default "data/senate".
#' @param issues Optional character vector of keywords to search for in lobbying
#'   activity descriptions (case-insensitive substring match).
#' @param issue_joiner "and" or "or" -- how multiple `issues` terms combine. Required if length(issues) > 1.
#' @param filing_period Optional exact match against the dataset's filing_period
#'   values: "first_quarter", "second_quarter", "third_quarter", "fourth_quarter"
#'   (also accepts "mid_year", "year_end" for older filings).
#' @param client_name Optional case-insensitive substring match against client name.
#' @param registrant_name Optional case-insensitive substring match against registrant name.
#' @param starting_date,ending_date Optional "YYYY-MM-DD" strings bounding `dt_posted`.
#' @param min_amount,max_amount Optional numeric bounds. Matches if EITHER income
#'   or expenses falls in range (the raw filing reports whichever applies to that
#'   registrant type) -- a simplification of the API's single "amount reported" filter.
#' @param tidy_result Logical (default TRUE). If TRUE, reduces to key columns
#'   (same whitelist as get_filings() plus the two carry-through columns below).
#' @param ignore_disclaimer Logical (default FALSE). Suppresses the double-counting disclaimer message.
#' @param cache_dir Where to cache each year's raw parsed frame (as .rds) so
#'   repeat calls skip the ~4-6 minute jsonlite parse of a full year. Set NULL to disable.
#'
#' @details
#' Adds two carry-through columns not present in get_filings() output, surfaced
#' as raw data for later analysis passes (not classified here):
#' \itemize{
#'   \item `covered_positions`: all lobbyists' `covered_position` text on the filing, semicolon-joined.
#'   \item `foreign_entities_flag` / `foreign_entity_names`: whether the filing lists foreign entities, and their names.
#' }
#'
#' @returns A data frame of quarterly filings, same shape as get_filings()'s output.
get_local_senate_filings <- function(years,
                                      data_root = "data/senate",
                                      issues = NULL,
                                      issue_joiner = NULL,
                                      filing_period = NULL,
                                      client_name = NULL,
                                      registrant_name = NULL,
                                      starting_date = NULL,
                                      ending_date = NULL,
                                      min_amount = NULL,
                                      max_amount = NULL,
                                      tidy_result = TRUE,
                                      ignore_disclaimer = FALSE,
                                      cache_dir = "skills/lobbying-quarterly-filings/.cache") {

  # --- 1. load + row-bind requested years ---------------------------------
  # jsonlite::fromJSON() on a full year of Senate filings (~100k+ deeply nested
  # records) takes 4-6 minutes REGARDLESS of flatten=TRUE/FALSE -- benchmarked
  # directly (230s vs 327s for the 2025 file), so this isn't a flatten-cost
  # problem, it's just an expensive parse. Cache the raw parsed frame per year
  # so repeat calls (e.g. exploring different filters/quarters) skip re-parsing.
  load_year <- function(year) {
    path <- file.path(data_root, year, "filings", paste0("filings_", year, ".json"))
    if (!file.exists(path)) {
      warning("No filings file for year ", year, " at ", path, " -- skipping.")
      return(NULL)
    }
    if (!is.null(cache_dir)) {
      cache_path <- file.path(cache_dir, paste0("senate_raw_", year, ".rds"))
      if (file.exists(cache_path) && file.info(cache_path)$mtime >= file.info(path)$mtime) {
        return(readRDS(cache_path))
      }
    }
    parsed <- jsonlite::fromJSON(path, flatten = TRUE)
    if (!is.null(cache_dir)) {
      dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
      saveRDS(parsed, file.path(cache_dir, paste0("senate_raw_", year, ".rds")))
    }
    parsed
  }
  # Mechanical fix (no method change): id-like columns parse as integer in most
  # years but character in 2024's JSON, which breaks bind_rows() on multi-year
  # calls. Harmonize them to character before combining.
  harmonize_id_types <- function(df) {
    if (is.null(df)) return(NULL)
    for (cl in names(df)[grepl("(^|\\.|_)id$", names(df))]) df[[cl]] <- as.character(df[[cl]])
    df
  }
  raw <- dplyr::bind_rows(lapply(purrr::map(years, load_year), harmonize_id_types))
  if (nrow(raw) == 0) {
    stop("No filings loaded for years: ", paste(years, collapse = ", "))
  }

  # --- 2. carry-through columns, computed before hoist/unnest discards the
  #        nested lobbying_activities/foreign_entities detail --------------
  extract_covered_positions <- function(activities_col) {
    purrr::map_chr(activities_col, function(la) {
      if (!is.data.frame(la) || nrow(la) == 0 || is.null(la$lobbyists)) return(NA_character_)
      positions <- unlist(purrr::map(la$lobbyists, function(lob) {
        if (!is.data.frame(lob) || nrow(lob) == 0 || is.null(lob$covered_position)) return(character(0))
        lob$covered_position[!is.na(lob$covered_position) & nzchar(lob$covered_position)]
      }))
      if (length(positions) == 0) return(NA_character_)
      paste(unique(positions), collapse = "; ")
    })
  }
  extract_foreign_entity_flag <- function(fe_col) {
    purrr::map_lgl(fe_col, function(fe) is.data.frame(fe) && nrow(fe) > 0)
  }
  extract_foreign_entity_names <- function(fe_col) {
    purrr::map_chr(fe_col, function(fe) {
      if (!is.data.frame(fe) || nrow(fe) == 0 || is.null(fe$name)) return(NA_character_)
      paste(unique(fe$name), collapse = "; ")
    })
  }
  extract_activities_text <- function(activities_col) {
    purrr::map_chr(activities_col, function(la) {
      if (!is.data.frame(la) || nrow(la) == 0 || is.null(la$description)) return("")
      paste(la$description[!is.na(la$description)], collapse = " ")
    })
  }

  raw <- raw |>
    dplyr::mutate(
      covered_positions = extract_covered_positions(lobbying_activities),
      foreign_entities_flag = extract_foreign_entity_flag(foreign_entities),
      foreign_entity_names = extract_foreign_entity_names(foreign_entities),
      .activities_text = extract_activities_text(lobbying_activities)
    )

  # --- 3. filters, mirroring the API's server-side query params ----------
  filtered <- raw

  if (!is.null(issues) && length(issues) > 0 && any(nzchar(issues))) {
    terms <- issues[nzchar(issues)]
    hits <- sapply(terms, function(term) {
      stringr::str_detect(stringr::str_to_lower(filtered$.activities_text), stringr::str_to_lower(term))
    })
    if (is.null(dim(hits))) hits <- matrix(hits, ncol = length(terms))
    joiner <- tolower(issue_joiner %||% "or")
    keep <- if (identical(joiner, "and")) apply(hits, 1, all) else apply(hits, 1, any)
    filtered <- filtered[keep, ]
  }
  if (!is.null(filing_period) && nzchar(filing_period)) {
    filtered <- filtered |> dplyr::filter(filing_period == !!filing_period)
  }
  if (!is.null(client_name) && nzchar(client_name)) {
    filtered <- filtered |> dplyr::filter(stringr::str_detect(stringr::str_to_lower(client.name), stringr::str_to_lower(!!client_name)))
  }
  if (!is.null(registrant_name) && nzchar(registrant_name)) {
    filtered <- filtered |> dplyr::filter(stringr::str_detect(stringr::str_to_lower(registrant.name), stringr::str_to_lower(!!registrant_name)))
  }
  if (!is.null(starting_date) && nzchar(starting_date)) {
    filtered <- filtered |> dplyr::filter(as.Date(dt_posted) >= as.Date(!!starting_date))
  }
  if (!is.null(ending_date) && nzchar(ending_date)) {
    filtered <- filtered |> dplyr::filter(as.Date(dt_posted) <= as.Date(!!ending_date))
  }
  if (!is.null(min_amount)) {
    min_amount <- as.numeric(min_amount)
    filtered <- filtered |> dplyr::filter((!is.na(income) & income >= min_amount) | (!is.na(expenses) & expenses >= min_amount))
  }
  if (!is.null(max_amount)) {
    max_amount <- as.numeric(max_amount)
    filtered <- filtered |> dplyr::filter((!is.na(income) & income <= max_amount) | (!is.na(expenses) & expenses <= max_amount))
  }

  filtered <- filtered |> dplyr::select(-.activities_text)

  # Mechanical fix (no method change): when the filters match zero filings,
  # hoist() on the empty frame never creates the issue-code columns and the
  # unnest below errors. Return the empty (0-row) result cleanly instead.
  if (nrow(filtered) == 0) {
    return(filtered |> dplyr::select(-lobbying_activities))
  }

  # --- 4. same hoist -> unnest -> pivot_wider pipeline get_filings() uses --
  data_to_work_with <- filtered |>
    tidyr::hoist(
      lobbying_activities,
      general_issue_code_display = "general_issue_code_display",
      description = "description"
    ) |>
    tidyr::unnest(c(general_issue_code_display, description), keep_empty = TRUE) |>
    dplyr::group_by(registrant.name, client.name) |>
    tidyr::pivot_wider(
      names_from = general_issue_code_display,
      values_from = description,
      values_fn = list
    ) |>
    dplyr::ungroup()

  cleaner_view <- function(dataframe_i_want_to_use, tidy_up_response = TRUE) {
    if (tidy_up_response) {
      dataframe_i_want_to_use |>
        dplyr::select(dplyr::any_of(c(
          "registrant.name", "client.name", "filing_type_display", "income", "expenses",
          "filing_year", "dt_posted", "filing_document_url", "registrant.description",
          "client.general_description", "filing_type", "filing_period",
          "registrant.id", "client.id", "registrant.house_registrant_id",
          "covered_positions", "foreign_entities_flag", "foreign_entity_names"
        )))
    } else {
      dataframe_i_want_to_use
    }
  }
  cleaned_data_to_work_with <- cleaner_view(data_to_work_with, tidy_up_response = tidy_result)

  if (!ignore_disclaimer) {
    message(
      "DISCLAIMER: This data is known to contain errors and requires additional filtering and cleaning to ensure correct results.\n",
      "Loaded from local corpus (data/senate), not the live lda.gov API -- same schema, same double-counting caveats.\n",
      "See flag_dupes() and flag_client_registrant_conflict() (scripts/lobbyr_clean.R) before aggregating spend."
    )
  }
  cleaned_data_to_work_with
}

`%||%` <- function(a, b) if (is.null(a)) b else a
