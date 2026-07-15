# Same rationale as classify_tax_theme.R, applied to cluster_actor_theme. Phase A's
# candidate_actor drafts turned out to follow a very regular "{org type} using {firm}" /
# "{org type} in-house" structure (1,472 distinct strings, but almost all built from the
# same small vocabulary of org-type nouns + a representation-mode suffix) -- so instead of
# merging strings, this re-derives the two facets directly and recombines them, which
# naturally bounds the vocabulary to org-type-count x 2 representation modes.
#
# Same fallback chain as classify_tax_theme.R when candidate_actor itself is too generic
# ("business entity", "entity", "organization"): fall back to client.general_description,
# then to the registrant's own stated firm type for oversized outside-firm buckets.

actor_org_type_rules <- list(
  list("Energy/utility/oil & gas company", "energy|utilit|oil and gas|electric|pipeline"),
  list("Insurance company", "insurance|reinsurance"),
  list("Financial services or investment firm", "financ|bank|invest|securities|asset management|private equity|hedge fund"),
  list("Pharmaceutical/biotech/healthcare company", "pharma|biotech|biopharma|health|hospital|medical"),
  list("Manufacturing or industrial company", "manufactur|industrial|automotive|steel|chemical"),
  list("Technology or media company", "technolog|media|streaming|software|internet"),
  list("Trade or industry association", "trade association|industry association|coalition|alliance|chamber"),
  list("Municipal or tribal government", "municipal government|tribal government|\\bcity\\b|\\bcounty\\b|public agency"),
  list("University or educational institution", "university|educational institution|college"),
  list("Retail, food, or agriculture company", "retail|food|beverage|agricultur|wholesale"),
  list("Labor union", "labor union|union"),
  list("Nonprofit or advocacy organization", "nonprofit|non-profit|advocacy|not-for-profit"),
  list("Professional sports or athlete organization", "athlete|professional sports|sports league")
)

actor_firm_type <- function(desc) {
  d <- tolower(desc)
  dplyr::case_when(
    stringr::str_detect(d, "law firm|law and legislative|lobbying law firm") ~ "law firm",
    stringr::str_detect(d, "lobbying|government (relations|affairs)|government consulting|legislative consulting") ~ "dedicated lobbying/government affairs firm",
    stringr::str_detect(d, "public affairs|strategic communications|pr firm") ~ "public affairs/strategic communications firm",
    TRUE ~ "unspecified firm type"
  )
}

#' Assign a final, cardinality-controlled cluster_actor_theme
#'
#' @param df A data frame with `candidate_actor`, `registrant.name`, `client.name`,
#'   `client.general_description`, and `registrant.description` columns.
#' @returns `df` with a `cluster_actor_theme` column added.
classify_tax_actor <- function(df) {
  text <- df$candidate_actor
  in_house <- stringr::str_detect(text, stringr::regex("in-house|in house", ignore_case = TRUE)) |
    (tolower(trimws(df$registrant.name)) == tolower(trimws(df$client.name)) & nzchar(df$registrant.name))

  org <- rep(NA_character_, nrow(df))
  for (rule in actor_org_type_rules) {
    hit <- is.na(org) & stringr::str_detect(text, stringr::regex(rule[[2]], ignore_case = TRUE))
    org[hit] <- rule[[1]]
  }
  needs_industry <- is.na(org)
  if (any(needs_industry)) {
    ind_text <- df$client.general_description[needs_industry]
    ind_org <- rep(NA_character_, length(ind_text))
    for (rule in actor_org_type_rules) {
      hit <- is.na(ind_org) & stringr::str_detect(ind_text, stringr::regex(rule[[2]], ignore_case = TRUE))
      ind_org[hit] <- rule[[1]]
    }
    org[needs_industry] <- ind_org
  }
  org[is.na(org)] <- "Business entity"

  rep_mode <- ifelse(in_house, "in-house", "using an outside lobbying firm")
  actor <- paste(org, rep_mode)

  # merge any under-10 org-type bucket into the generic "Business entity" sibling
  counts <- table(actor)
  under10 <- names(counts)[counts < 10]
  is_under10 <- actor %in% under10
  actor[is_under10] <- paste("Business entity", rep_mode[is_under10])

  # split any remaining over-200 outside-firm bucket by the registrant's own stated firm
  # type (real metadata) -- mirrors classify_tax_theme.R's residual fallback
  counts <- table(actor)
  over200_outside <- names(counts)[counts > 200 & grepl("outside", names(counts))]
  is_over <- actor %in% over200_outside
  if (any(is_over)) {
    base <- sub(" using an outside lobbying firm$", "", actor[is_over])
    actor[is_over] <- paste0(base, " using outside firm (", actor_firm_type(df$registrant.description[is_over]), ")")
  }

  # re-merge any now-under-10 firm-type slice into an "unspecified" sibling
  counts <- table(actor)
  under10 <- names(counts)[counts < 10]
  is_under10 <- actor %in% under10
  actor[is_under10] <- paste0(sub(" \\(.*\\)$", "", actor[is_under10]), " (unspecified firm type)")

  df$cluster_actor_theme <- actor
  df
}
