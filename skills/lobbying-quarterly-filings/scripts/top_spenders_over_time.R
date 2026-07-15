# Deterministic rollup that answers "who's spending more or less over time" --
# meant to be called on the *already cleaned* output of flag_dupes() +
# flag_client_registrant_conflict() so totals aren't inflated by duplicate or
# double-counted filings. Works on either Senate or House loader output since
# both share the registrant.name/client.name/filing_year/filing_period/income/
# expenses column vocabulary.

quarter_num_lookup <- c(first_quarter = 1L, second_quarter = 2L, third_quarter = 3L, fourth_quarter = 4L)

#' Rank entities by lobbying spend across quarters, with quarter-over-quarter deltas
#'
#' @param df A cleaned filings data frame (post flag_dupes/flag_client_registrant_conflict).
#' @param entity_col Which column identifies the spender: "client.name" (who's
#'   paying for lobbying) or "registrant.name" (who's being paid). Default "client.name".
#' @param metric Which amount column to sum: "income" or "expenses". Default "expenses".
#' @param n How many top entities (by total spend across all quarters) to keep. Default 20.
#'
#' @details
#' Rows with a filing_period outside the four standard quarters (e.g. legacy
#' "mid_year"/"year_end" filings) are dropped -- this function is quarter-over-quarter
#' by design. Rows with a missing/non-numeric metric value are dropped from the sum.
#'
#' @returns A list with three data frames:
#' \itemize{
#'   \item `long`: one row per entity per quarter, with `total`, `n_filings`,
#'     `prev_total`, `change_abs`, `change_pct`, and `rank_in_quarter`.
#'   \item `wide`: entity x quarter matrix of `total` spend (easiest for eyeballing trends).
#'   \item `entity_totals`: each top entity's grand total across all quarters, ranked.
#' }
top_spenders_over_time <- function(df, entity_col = "client.name", metric = "expenses", n = 20) {
  stopifnot(entity_col %in% names(df), metric %in% names(df))

  work <- df |>
    dplyr::filter(!is.na(.data[[entity_col]]), filing_period %in% names(quarter_num_lookup)) |>
    dplyr::mutate(
      entity = .data[[entity_col]],
      quarter_num = quarter_num_lookup[filing_period],
      quarter_label = sprintf("%d-Q%d", filing_year, quarter_num),
      metric_value = suppressWarnings(as.numeric(.data[[metric]]))
    ) |>
    dplyr::filter(!is.na(metric_value))

  by_entity_quarter <- work |>
    dplyr::group_by(entity, filing_year, quarter_num, quarter_label) |>
    dplyr::summarise(total = sum(metric_value), n_filings = dplyr::n(), .groups = "drop")

  entity_totals <- by_entity_quarter |>
    dplyr::group_by(entity) |>
    dplyr::summarise(grand_total = sum(total), .groups = "drop") |>
    dplyr::arrange(dplyr::desc(grand_total))

  top_entities <- utils::head(entity_totals$entity, n)

  long <- by_entity_quarter |>
    dplyr::filter(entity %in% top_entities) |>
    dplyr::arrange(entity, filing_year, quarter_num) |>
    dplyr::group_by(entity) |>
    dplyr::mutate(
      prev_total = dplyr::lag(total),
      change_abs = total - prev_total,
      change_pct = dplyr::if_else(!is.na(prev_total) & prev_total != 0, (total - prev_total) / prev_total * 100, NA_real_)
    ) |>
    dplyr::ungroup() |>
    dplyr::group_by(quarter_label) |>
    dplyr::mutate(rank_in_quarter = dplyr::min_rank(dplyr::desc(total))) |>
    dplyr::ungroup()

  wide <- long |>
    dplyr::select(entity, quarter_label, total) |>
    tidyr::pivot_wider(names_from = quarter_label, values_from = total)

  list(
    long = long,
    wide = wide,
    entity_totals = entity_totals |> dplyr::filter(entity %in% top_entities)
  )
}
