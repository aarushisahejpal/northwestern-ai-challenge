# Deterministic final-assignment classifier for cluster_lobbying_activity_theme, built
# from Phase A's LLM-drafted activity_summary/candidate_theme text. This is Phase B/C of
# the theme-clustering pipeline (see SKILL.md): Phase A (subagents, one per row-batch)
# drafts free-text candidate labels; those turned out extremely fragmented (1,458 distinct
# candidate_theme strings across 2,906 rows, since each batch drafted independently with no
# shared vocabulary) and a meaningful share defaulted to vague labels ("General tax policy")
# even when the row's own activity_summary had a specific mechanism sitting right there.
# Rather than hand-merge ~1,458 strings, this reconciles all of it with a keyword ruleset
# tuned directly against this dataset's real label distribution -- deterministic, auditable,
# and reproducible, instead of another LLM pass over already-drafted text.
#
# Priority order matters: rules are checked top to bottom, first match wins. More specific
# mechanisms (gold, tobacco, hydrogen, ...) are listed before broader ones (clean energy,
# corporate tax reform, ...) so a specific mention doesn't get swallowed by a generic rule.

tax_theme_rules <- list(
  list("Gold and precious metals tax treatment", "\\bgold\\b|precious metal|bullion|silver mining"),
  list("Tobacco and nicotine excise taxes", "tobacco|nicotine|\\bcigar|vapor|vaping|e-cigarette"),
  list("Taxation of sports, wagering, and athlete income", "sports betting|wagering|sportsbook|gaming excise|gaming tax|athlete income|sports and entertainment facility|taxation of sports"),
  list("Cryptocurrency and digital asset taxation", "crypto|digital asset|blockchain|virtual currency|stablecoin"),
  list("Carbon capture tax credits (45Q)", "carbon capture|\\b45q\\b|carbon sequestration"),
  list("Advanced manufacturing and semiconductor tax credits", "semiconductor|advanced manufacturing|\\b45x\\b|chips act"),
  list("Hydrogen and clean fuel production tax credits", "hydrogen|sustainable aviation fuel|\\bsaf\\b|clean fuel|biofuel|biodiesel|renewable fuel|biomass"),
  list("Electric vehicle and clean vehicle tax credits", "electric vehicle|\\bev\\b credit|clean vehicle|ev tax credit"),
  list("Renewable and nuclear energy production tax credits (solar/wind/geothermal/nuclear)", "nuclear energy|nuclear power|nuclear.{0,10}tax credit|solar|wind energy|geothermal|energy storage tax"),
  list("Digital services, media, and telecom tax treatment", "digital service|streaming tax|media and film|film and television|telecommunications|technology sector taxation"),
  list("Clean energy tax credits (IRA/OBBBA and reconciliation bill implementation)", "inflation reduction act|\\bobbba\\b|energy.{0,20}reconciliation|reconciliation.{0,20}energy"),
  list("Clean energy tax credits (general mechanisms)", "renewable energy|clean energy|clean electricity|clean technology|energy investment credit|energy production tax credit|energy production and|\\bptc\\b|\\bitc\\b|\\bsection 45\\b|\\bsection 48\\b|energy tax credit|energy efficiency|energy tax policy|linear generator|utility.{0,15}tax (credit|incentive)"),
  list("Transportation, aviation, and shipping tax provisions", "railroad|shipping|maritime|aviation industry|transportation.{0,15}infrastructure tax|transportation tax credit"),
  list("Research credit and full expensing", "research and development|r&d (tax|credit)|research credit|full expensing|\\bsection 174\\b|r&d expensing|orphan drug|medical device|biotech taxation"),
  list("Low-income housing and community development tax credits", "low-income housing|\\blihtc\\b|affordable housing tax|new markets tax credit|community development"),
  list("Opportunity zones and real estate investment taxation", "opportunity zone|real estate investment trust|\\breit\\b|real estate and housing|historic preservation|like-kind exchange"),
  list("Tax-exempt municipal bond treatment", "municipal bond|tax-exempt bond|advance refunding|private activity bond"),
  list("Estate, gift, and trust taxation", "estate tax|gift tax|trust taxation|generation-skipping|estate and transfer"),
  list("Capital gains, carried interest, and investment fund taxation", "carried interest|capital gains tax treatment|venture capital|business development company|investment industry taxation|regulated investment company"),
  list("Retirement and pension tax provisions", "retirement|pension|401\\(k\\)|401\\(h\\)|\\besop\\b|employee stock ownership|\\bira\\b|annuity"),
  list("Life insurance and PPLI tax treatment", "life insurance|\\bppli\\b"),
  list("Health savings accounts and premium tax credits", "health savings|\\bhsa\\b|premium tax credit|health.{0,15}premium"),
  list("Employment, payroll, and worker tax credits", "work opportunity tax credit|\\bwotc\\b|employment.{0,10}credit|payroll tax credit|employee retention.{0,10}credit|overtime compensation|first responder|occupational injury"),
  list("Child, dependent care, and education tax credits", "child tax credit|dependent care|child.?care|education credit|\\b529\\b|school choice|scholarship"),
  list("Foreign tax credits and international tax rules", "foreign tax credit|international tax|\\boecd\\b|pillar (one|two|1|2)|\\bbeat\\b|base erosion|\\bgilti\\b|global minimum tax|international corporate|\\bfatca\\b|\\bfbar\\b|foreign account|section 899|overseas american"),
  list("Charitable giving and nonprofit/endowment taxation", "charitable|donor advised fund|nonprofit tax|tax-exempt organization|endowment taxation|university endowment|college endowment"),
  list("Insurance industry tax provisions", "insurance compan|reinsurance|insurance product tax|annuity taxation|property and casualty insurance|insurance provisions|insurance tax provisions"),
  list("Banking and financial services taxation", "\\bbank\\b|financial institution|financial services tax|financial transaction tax"),
  list("Agricultural and food industry tax provisions", "agricultur|\\bfarm\\b|food industry tax|hospitality and lodging"),
  list("Excise taxes (fuel, alcohol, firearms, cannabis)", "excise tax|alcohol tax|firearm|gasoline tax|motor fuel tax|motor fuel|\\bbeer\\b|brewer|distiller|\\bwine\\b|beverage excise|cannabis"),
  list("Pass-through entity and small business taxation", "pass-through|qualified business income|\\bqbi\\b|s-corp|s corporation|small business tax"),
  list("Tariffs and trade tax provisions", "tariff|trade tax|import dut|customs dut"),
  list("Tax administration, compliance, and IRS matters", "tax administration|tax preparation|irs administration|tax compliance"),
  list("Corporate tax rate and reform provisions", "corporate tax rate|corporate income tax|corporate tax reform|corporate taxation|alternative minimum tax|\\bamt\\b|corporate and international|comprehensive tax reform|general corporate tax|general tax and trade"),
  list("Tax Cuts and Jobs Act (TCJA) extension monitoring", "tax cuts and jobs act|\\btcja\\b|2017 tax"),
  list("2025 tax reconciliation bill and budget monitoring", "reconciliation bill|one big beautiful|budget reconciliation|\\bh\\.?r\\.? ?1\\b|budget for fiscal year|congressionally directed spending|tax reconciliation provisions"),
  list("Manufacturing and industrial tax incentives", "manufactur")
)

# Fallback #1 when no mechanism keyword matches anything in activity_summary/candidate_theme:
# the client's own industry (client.general_description) is the most specific truthful
# signal left -- not a fabricated label, and not "Other"/"General tax".
industry_rules <- list(
  list("energy, utility, or oil & gas company", "energy|utilit|oil and gas|electric power|pipeline"),
  list("healthcare or pharmaceutical organization", "health|hospital|pharma|medical|biotech"),
  list("financial services or investment firm", "financ|bank|invest|securities|asset management|insurance|private equity|hedge fund"),
  list("manufacturing or industrial company", "manufactur|industrial|steel|chemical"),
  list("technology or telecommunications company", "technolog|software|telecommunications|internet"),
  list("trade or membership association", "association|chamber|council|coalition|alliance"),
  list("municipal or state government entity", "municipal|city of|county of|state of|government"),
  list("retail, hospitality, or consumer products company", "retail|restaurant|hospitality|consumer"),
  list("real estate or construction company", "real estate|construction|housing|property"),
  list("professional services, education, or nonprofit/advocacy organization", "law firm|consult|higher education|university|nonprofit|non-profit|not-for-profit|advocacy|thinktank|think tank|labor union"),
  list("transportation, aerospace, or logistics company", "airline|aerospace|port authority|freight|logistics|shipping|maritime")
)

# Fallback #2, only reached if fallback #1 is itself over 200 rows: registrant.name ==
# client.name (in-house vs. outside firm) is real filing metadata, not fabricated.
# Fallback #3, only reached if the outside-firm slice is itself still over 200: the
# registrant's own stated firm type (registrant.description) -- also real metadata.

#' Assign a final, cardinality-controlled cluster_lobbying_activity_theme
#'
#' @param df A data frame with `activity_summary`, `candidate_theme`, `client.general_description`,
#'   `registrant.name`, `client.name`, `registrant.description` columns (the first two from
#'   Phase A's LLM drafting pass; the rest from the original filing metadata).
#' @returns `df` with a `cluster_lobbying_activity_theme` column added.
classify_tax_theme <- function(df) {
  text <- paste(df$activity_summary, df$candidate_theme)
  theme <- rep(NA_character_, nrow(df))
  for (rule in tax_theme_rules) {
    hit <- is.na(theme) & stringr::str_detect(text, stringr::regex(rule[[2]], ignore_case = TRUE))
    theme[hit] <- rule[[1]]
  }

  needs_industry <- is.na(theme)
  if (any(needs_industry)) {
    ind_text <- df$client.general_description[needs_industry]
    ind_theme <- rep(NA_character_, length(ind_text))
    for (rule in industry_rules) {
      hit <- is.na(ind_theme) & stringr::str_detect(ind_text, stringr::regex(rule[[2]], ignore_case = TRUE))
      ind_theme[hit] <- paste0("General federal tax policy monitoring (", rule[[1]], ")")
    }
    ind_theme[is.na(ind_theme)] <- "General federal tax policy monitoring (other/unspecified clients)"
    theme[needs_industry] <- ind_theme
  }
  df$cluster_lobbying_activity_theme <- theme

  # merge any under-10 bucket back into the generic residual -- includes both rare industry
  # matches and rare mechanism matches (e.g. "Gold and precious metals tax treatment" landed
  # at ~5 rows in the 2026 Q1 TAX run; a real, recognizable theme that still can't stand on
  # its own under the 10-row floor)
  counts <- table(df$cluster_lobbying_activity_theme)
  under10 <- names(counts)[counts < 10 & counts > 0 &
    names(counts) != "General federal tax policy monitoring (other/unspecified clients)"]
  df$cluster_lobbying_activity_theme[df$cluster_lobbying_activity_theme %in% under10] <-
    "General federal tax policy monitoring (other/unspecified clients)"

  # last-resort splits, only triggered if the residual is still over 200
  other <- "General federal tax policy monitoring (other/unspecified clients)"
  is_other <- df$cluster_lobbying_activity_theme == other
  if (sum(is_other) > 200) {
    in_house <- tolower(trimws(df$registrant.name)) == tolower(trimws(df$client.name))
    df$cluster_lobbying_activity_theme[is_other & in_house] <- "General federal tax policy monitoring (self-filed, in-house)"
    df$cluster_lobbying_activity_theme[is_other & !in_house] <- "General federal tax policy monitoring (filed via outside lobbying firm)"
  }

  outside <- "General federal tax policy monitoring (filed via outside lobbying firm)"
  is_outside <- df$cluster_lobbying_activity_theme == outside
  if (sum(is_outside) > 200) {
    desc <- tolower(df$registrant.description[is_outside])
    firm_type <- dplyr::case_when(
      stringr::str_detect(desc, "law firm|law and legislative|lobbying law firm") ~ "law firm",
      stringr::str_detect(desc, "lobbying|government (relations|affairs)|government consulting|legislative consulting") ~ "dedicated lobbying/government affairs firm",
      stringr::str_detect(desc, "public affairs|strategic communications|pr firm") ~ "public affairs/strategic communications firm",
      TRUE ~ "unspecified firm type"
    )
    df$cluster_lobbying_activity_theme[is_outside] <- paste0("General federal tax policy monitoring (outside firm - ", firm_type, ")")
  }

  df
}
