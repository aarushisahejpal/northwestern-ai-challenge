# Orchestrates the full theme-clustering pipeline for one issue-area subset:
#   1. prepare_issue_subset() -- load + slice the local Senate corpus (Part 1 of SKILL.md)
#   2. read back the Phase A subagent drafts (one JSONL file per row-batch; produced
#      outside this script, by an agent orchestrator following references/batch_prompt.md)
#   3. classify_tax_theme() / classify_tax_actor() -- deterministic Phase B/C consolidation
#   4. build_cluster_and_reasoning() -- derive `cluster` + finalize `cluster_reasoning`
#   5. write the original subset's columns, untouched, plus the five new columns appended
#
# This script is written for the TAX (Taxation/Internal Revenue Code) run specifically --
# classify_tax_theme.R/classify_tax_actor.R's keyword rules were tuned against that issue
# area's real label distribution. Re-running for a different issue area means re-tuning
# those two rule sets against the new distribution (see references/column_spec.md).

library(dplyr)

`%||%` <- function(a, b) if (is.null(a)) b else a

here <- "skills/lobbying-issue-theme-clustering/scripts"
senate_here <- "skills/lobbying-quarterly-filings/scripts"

source(file.path(senate_here, "local_senate_filings.R"))
source(file.path(here, "prepare_issue_subset.R"))
source(file.path(here, "classify_tax_theme.R"))
source(file.path(here, "classify_tax_actor.R"))
source(file.path(here, "build_cluster_and_reasoning.R"))

#' Read Phase A's per-batch JSONL drafts back into one data frame
#'
#' @param jsonl_dir Directory containing batch_*.jsonl files (row_id, activity_summary,
#'   candidate_theme, candidate_actor, posture, cluster_reasoning_draft per line).
#' @returns A data frame keyed by row_id (as character, since some batches write it as a
#'   JSON number and others as a JSON string -- normalize on read).
read_phase_a_drafts <- function(jsonl_dir) {
  files <- list.files(jsonl_dir, pattern = "\\.jsonl$", full.names = TRUE)
  rows <- purrr::map(files, function(f) {
    lines <- readLines(f, warn = FALSE)
    lines <- lines[nzchar(trimws(lines))]
    purrr::map_dfr(lines, function(l) {
      d <- jsonlite::fromJSON(l)
      tibble::tibble(
        row_id = as.character(d$row_id),
        activity_summary = d$activity_summary,
        candidate_theme = d$candidate_theme %||% d$candidate_team,  # tolerate the one observed key typo
        candidate_actor = d$candidate_actor,
        posture = d$posture,
        cluster_reasoning_draft = d$cluster_reasoning_draft
      )
    })
  })
  dplyr::bind_rows(rows)
}

#' Run the full pipeline for one issue-area subset
#'
#' @param years,issue_names,... passed straight through to prepare_issue_subset().
#' @param jsonl_dir Directory of Phase A drafts, keyed by the same row_id scheme
#'   prepare_issue_subset() assigns (sequential integer, assigned before batching).
#' @returns The original subset's columns, untouched, plus activity_summary,
#'   cluster_lobbying_activity_theme, cluster_actor_theme, cluster, cluster_reasoning.
run_theme_clustering_pipeline <- function(years, issue_names, jsonl_dir, ...) {
  subset_df <- prepare_issue_subset(years = years, issue_names = issue_names, ...)
  subset_df$row_id <- as.character(seq_len(nrow(subset_df)))

  drafts <- read_phase_a_drafts(jsonl_dir)
  stopifnot(nrow(drafts) == nrow(subset_df))  # every row must have been classified, per spec

  merged <- dplyr::left_join(subset_df, drafts, by = "row_id")
  merged <- classify_tax_theme(merged)
  merged <- classify_tax_actor(merged)
  merged <- build_cluster_and_reasoning(merged)

  # spec: return the full original data with the five new columns appended, nothing
  # removed/reordered. Drop only the internal join key and Phase A's unfinalized drafts.
  merged |>
    dplyr::select(-row_id, -candidate_theme, -candidate_actor, -cluster_reasoning_draft)
}
