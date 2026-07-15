# Final assembly of `cluster` and `cluster_reasoning` from the already-finalized
# cluster_lobbying_activity_theme (classify_tax_theme.R) and cluster_actor_theme
# (classify_tax_actor.R) columns, plus the row-level posture and reasoning draft Phase A
# already produced.
#
# Two correctness bugs found by spot-checking real output, not assumed, and fixed here:
#
# 1. An earlier version derived `cluster` from each THEME's single dominant actor pattern,
#    applied to every row in that theme. On the real 2026 Q1 TAX run, that mislabeled 1,701
#    of 2,906 rows (58%) with an actor type that didn't match their own `cluster_actor_theme`
#    (e.g. a payments-company filing labeled "Pharmaceutical/biotech company shaping..."
#    because pharma happened to be that theme's most common actor). Fixed by deriving
#    `cluster` from each row's OWN actor + posture, not the theme's aggregate.
#
# 2. A per-ROW cascading fallback (fall back to a coarser label only for rows whose exact
#    combo was rare) looked right but produces small leftover residuals: most rows of a
#    theme find a fine-grained (actor, posture) home with plenty of company, and only a
#    sparse few don't -- cascading *just those few* down still leaves an under-10 bucket.
#    Fixed by deciding the split granularity per THEME as a whole (finest grain where every
#    sub-bucket in that theme clears 10 rows; otherwise the whole theme uses one coarser
#    label), never a mixed per-row cascade.

posture_verb <- c(offense = "shaping", defense = "defending", monitoring = "monitoring")

# IMPORTANT: must stay 1:1 with cluster_lobbying_activity_theme -- never collapse two
# distinct final themes to the same string here (e.g. an earlier version stripped every
# parenthetical, which merged all 14 "General federal tax policy monitoring (X)" variants,
# and both Clean energy sub-themes, into one string each -- silently re-merging buckets
# the cardinality-controlled classifier had deliberately kept separate). Only cosmetic,
# non-distinguishing wordiness is trimmed; every parenthetical qualifier that carries real
# distinguishing content (an industry, a bill name, a firm type) is kept.
shorten_theme <- function(theme) {
  theme <- gsub("^General federal tax policy monitoring \\(", "federal tax policy (", theme)
  theme <- gsub(" and reform provisions$| and legislative monitoring$", "", theme)
  theme
}

strip_actor_suffix <- function(actor) {
  gsub(" using an outside lobbying firm.*| in-house", "", actor)
}

#' Build the `cluster` narrative-title column and finalize `cluster_reasoning`
#'
#' @param df A data frame with `cluster_lobbying_activity_theme`, `cluster_actor_theme`,
#'   `posture`, and `cluster_reasoning_draft` columns already populated.
#' @returns `df` with `cluster` and `cluster_reasoning` columns added.
build_cluster_and_reasoning <- function(df) {
  actor_short <- strip_actor_suffix(df$cluster_actor_theme)
  posture_norm <- ifelse(tolower(df$posture) %in% names(posture_verb), tolower(df$posture), "monitoring")
  theme_short <- shorten_theme(df$cluster_lobbying_activity_theme)

  level1 <- paste(stringr::str_to_sentence(actor_short), posture_verb[posture_norm], theme_short)
  level2 <- paste("Multiple actor types", posture_verb[posture_norm], theme_short)
  level3 <- paste("Filings on", theme_short)

  cluster <- character(nrow(df))
  for (th in unique(df$cluster_lobbying_activity_theme)) {
    idx <- which(df$cluster_lobbying_activity_theme == th)
    l1 <- level1[idx]
    if (min(table(l1)) >= 10) {
      cluster[idx] <- l1
      next
    }
    l2 <- level2[idx]
    if (min(table(l2)) >= 10) {
      cluster[idx] <- l2
      next
    }
    cluster[idx] <- level3[idx]  # whole theme, one label -- inherits the theme's own count (>=10)
  }

  df$cluster <- cluster
  df$cluster_reasoning <- paste0(
    df$cluster_reasoning_draft,
    " This places the filing in the '", df$cluster, "' cluster (",
    df$cluster_lobbying_activity_theme, " / ", df$cluster_actor_theme, ")."
  )
  df
}
