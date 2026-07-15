####### Load necessary libraries for the app's functionality
library(shiny)
library(bslib)
library(DT)
library(shinyjs)
library(dplyr)

####### Source the local-data equivalents of lobbyR, instead of library(lobbyR) + the live API.
####### No API key / keyring needed -- everything here reads data/senate/ directly.
source("skills/lobbying-quarterly-filings/scripts/local_senate_filings.R")
source("skills/lobbying-quarterly-filings/scripts/lobbyr_clean.R")
source("skills/lobbying-quarterly-filings/scripts/top_spenders_over_time.R")
source("skills/lobbying-quarterly-filings/scripts/top_spenders_by_issue.R")

ENRICHED_TAX_PATH <- "skills/lobbying-issue-theme-clustering/output/tax_2026q1_enriched.rds"

####### Build the ALI code dropdown choices once at app start ("CODE — Name" -> "CODE")
ali_code_choices <- {
  codes <- list_ali_codes()
  stats::setNames(codes$code, paste0(codes$code, " — ", codes$name))
}

####### Helper function to build a string representing the get_local_senate_filings() call
####### with the user's parameters -- same idea as app.R's build_call_string(), retargeted.
build_call_string <- function(params) {
  format_value <- function(x) {
    if (length(x) == 0) return("NULL")
    if (is.character(x) && all(x == "")) return("NULL")
    if (is.null(x)) return("NULL")

    if (is.character(x) && length(x) > 1) {
      return(paste0('c("', paste(x, collapse = '", "'), '")'))
    }
    if (is.character(x)) return(paste0('"', x, '"'))
    if (is.logical(x)) return(ifelse(x, "T", "F"))
    x
  }

  sprintf(
    'get_local_senate_filings(\n  issues = %s,\n  issue_joiner = %s,\n  years = %s,\n  filing_period = %s,\n  client_name = %s,\n  registrant_name = %s,\n  ending_date = %s,\n  starting_date = %s,\n  tidy_result = %s,\n  ignore_disclaimer = %s\n)',
    format_value(params$issues),
    format_value(params$issue_joiner),
    format_value(params$years),
    format_value(params$filing_period),
    format_value(params$client_name),
    format_value(params$registrant_name),
    format_value(params$ending_date),
    format_value(params$starting_date),
    format_value(params$tidy_result),
    format_value(params$ignore_disclaimer)
  )
}

####### Shared DT rendering helper -- reused by the search tab and its cleaning-helper redraws
render_filings_table <- function(df) {
  if (is.null(df)) {
    return(datatable(data.frame(Error = "No data"), rownames = FALSE))
  }
  col_rename <- c(
    "registrant.name" = "registrant",
    "client.name" = "client",
    "filing_type_display" = "filing type",
    "dt_posted" = "date posted",
    "filing_document_url" = "filing url",
    "registrant.description" = "registrant description",
    "client.general_description" = "client description",
    "filing_type" = "filing code",
    "filing_period" = "filing period"
  )
  df <- as.data.frame(df)
  old_names <- names(df)
  names(df) <- ifelse(old_names %in% names(col_rename), col_rename[old_names], old_names)
  if ("filing url" %in% names(df)) {
    df[["filing url"]] <- ifelse(
      is.na(df[["filing url"]]) | df[["filing url"]] == "",
      "",
      sprintf('<a href="%s" target="_blank">%s</a>', df[["filing url"]], df[["filing url"]])
    )
  }
  if ("income" %in% names(df)) df$income <- as.numeric(gsub("[^0-9.-]", "", df$income))
  if ("expenses" %in% names(df)) df$expenses <- as.numeric(gsub("[^0-9.-]", "", df$expenses))
  dt <- datatable(
    df,
    options = list(pageLength = -1, scrollX = TRUE, scrollY = "600px", dom = "Bfrtip"),
    filter = "top",
    rownames = FALSE,
    escape = FALSE
  )
  if ("income" %in% names(df)) dt <- DT::formatCurrency(dt, "income", currency = "$", digits = 2)
  if ("expenses" %in% names(df)) dt <- DT::formatCurrency(dt, "expenses", currency = "$", digits = 2)
  dt
}

####### Define the user interface (UI) for the app
ui <- page_fluid(
  tags$head(
    tags$style(HTML("
    /* === General App Layout === */
    p { font-size: 0.8em; }
    .label { font-size: 1em; }
    #main_status {
      width: 100%;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-x: hidden;
    }

    /* === Action Buttons === */
    #actionbuttons { padding: 0.2em 0 0.2em 0; }
    button.action-button { margin: 0.2em; }

    /* === Cleaning Helpers Box === */
    #cleaning_helpers {
      border: 2px solid red;
      padding: 10px;
      border-radius: 5px;
    }

    /* === Disclaimer Section === */
    #disclaimer { font-size: 0.8em; }

    /* === DataTable Styling === */
    #data_table, #cluster_data_table {
      height: 500px;
      overflow-y: auto;
    }
    #data_table table.dataTable, #cluster_data_table table.dataTable { margin: 0 !important; }
    table.dataTable th, table.dataTable td {
      max-width: 225px;
      overflow: hidden;
      white-space: nowrap;
      word-wrap: break-word;
    }
    .dataTables_wrapper .dataTables_scrollBody {
      overflow-x: scroll !important;
      overflow-y: scroll !important;
    }
    .dataTables_scrollHead { overflow-x: scroll !important; }
  "))
  ),
  shinyjs::useShinyjs(),
  theme = bslib::bs_theme(
    version = 5, bootswatch = "journal",
    bg = "#0b3d91", fg = "white", primary = "#FCC780",
    base_font = font_collection(font_google("Roboto", local = FALSE), "Pacifico", "sans-serif")
  ),
  titlePanel("Lobbying disclosures: local corpus explorer (no API key required)"),
  navset_tab(
    ##### TAB 1: search, modeled on app.R's lobbyR-live-API form, retargeted to local data
    nav_panel(
      "Search Filings",
      sidebarLayout(
        sidebarPanel(
          actionLink("toggleMath", "Quick math"),
          shinyjs::hidden(
            div(id = "math_dropdown",
                p("This gives a quick ballpark on how much income or expenses an entity might have spent on lobbying."),
                p("DISCLAIMER: Use checkers and inspect data to make sure the number is accurate."),
                actionButton("sum_totals", "Sum totals", class = "btn-primary")
            )
          ),
          div(id = "myapp",
              textInput("issues", "Issues (comma-separated)", value = ""),
              radioButtons("issue_joiner", "Issue Joiner:", choices = c("and", "or"), selected = "", inline = TRUE),
              selectInput("years", "Year(s)", choices = 2022:2026, selected = 2026, multiple = TRUE),
              textInput("client_name", "Client Name (one client only)", value = ""),
              checkboxInput("ignore_disclaimer", "Ignore Disclaimer", value = FALSE),
              checkboxInput("tidy_result", "Avoid raw data", value = TRUE),
              div(actionLink("toggleAdvanced", "Show/Hide search fields"), style = "margin-bottom: 0.5em;"),
              shinyjs::hidden(
                div(id = "advanced",
                    textInput("registrant_name", "Registrant Name (one registrant only)", value = ""),
                    selectInput("filing_period", "Filing Period",
                                choices = c("", "first_quarter", "second_quarter", "third_quarter", "fourth_quarter")),
                    dateInput("starting_date", "Starting Date", value = "2022-01-01", format = "yyyy-mm-dd"),
                    dateInput("ending_date", "Ending Date", value = NULL, format = "yyyy-mm-dd"),
                    textInput("min_amount", "Minimum Amount (USD)", value = ""),
                    textInput("max_amount", "Maximum Amount (USD)", value = ""),
                    width = 12
                )
              ),
              div(id = "actionbuttons",
                  actionButton("query", "Query Filings"),
                  actionButton("reset", "Reset Form")
              ),
              div(id = "cleaning_helpers",
                  h5("Data cleaning options:"),
                  h6("Use these once you've made your query to try and clean the data"),
                  br(),
                  actionLink("toggledupes", "Show dupe checker"),
                  shinyjs::hidden(
                    div(id = "dupes",
                        radioButtons("dupes_group", "Checkbox group",
                                     choices = c("Flag duplicates" = "a", "Attempt to clean" = "b", "Revert to original data" = "c"),
                                     selected = character(0))
                    )
                  ),
                  br(),
                  actionLink("toggleconflict", "Show conflict checker"),
                  shinyjs::hidden(
                    div(id = "conflict",
                        radioButtons("conflict_group", "Check for Conflict",
                                     choices = c("Flag conflicts" = "a", "Attempt to clean" = "b", "Revert to original data" = "c"),
                                     selected = character(0))
                    )
                  ),
                  br(), br(), br(),
                  div(id = "disclaimer",
                      p("Cleaning uses this project's vendored ",
                        tags$code("flag_dupes()"), " and ", tags$code("flag_client_registrant_conflict()"),
                        " (from lobbyR, ported to run on local data) -- read ",
                        tags$a(href = "https://github.com/Lobbying-DisclosuRe/lobbyr?tab=readme-ov-file#flag_dupes", "flag_dupes"),
                        " and ",
                        tags$a(href = "https://github.com/Lobbying-DisclosuRe/lobbyr/blob/main/README.md#flag_client_registrant_conflict", "flag_client_registrant_conflict"),
                        " before using these options to understand how they may impact your data."),
                      h6("!IMPORTANT: If after using cleaning data functions a user wants to just go back to flagging it, you must select revert to original data before doing so or else you may get an inaccurate count.")
                  )
              )
          ),
          width = 3
        ),
        mainPanel(
          h4("Interactive DataTable"),
          downloadButton("download_all", "Download All Results"),
          DTOutput("data_table"),
          h4("Status/Response"),
          verbatimTextOutput("main_status"),
          h5("Query readout"),
          verbatimTextOutput("results"),
          width = 9
        )
      )
    ),
    ##### TAB 2: new -- explore the LLM-enriched thematic clusters
    nav_panel(
      "Thematic Clusters",
      sidebarLayout(
        sidebarPanel(
          p("Explore filings enriched with activity_summary/cluster columns from the",
            tags$code("lobbying-issue-theme-clustering"), "skill."),
          uiOutput("cluster_theme_picker"),
          width = 3
        ),
        mainPanel(
          plotOutput("cluster_counts_plot", height = "300px"),
          h4("Filings in selected theme"),
          DTOutput("cluster_data_table"),
          width = 9
        )
      )
    ),
    ##### TAB 3: new -- rank spenders by ALI issue code, with a fact-checkable raw-filings view.
    ##### Every input ID here is fresh (ts_-prefixed, or ali_-prefixed for the two ALI-specific
    ##### controls) so nothing collides with Tab 1's issues/issue_joiner/years/etc -- Shiny
    ##### input IDs are global across the whole app, not scoped per tab.
    nav_panel(
      "Top Spenders by Issue",
      sidebarLayout(
        sidebarPanel(
          p("Rank lobbying spend within one or more 3-letter ALI issue codes (see",
            tags$code("data/senate/constants/lobbying_activity_issues.json"), "for the full list)."),
          selectInput("ali_codes", "ALI Issue Code(s)", choices = ali_code_choices, multiple = TRUE),
          radioButtons("ali_issue_joiner", "Match:",
                       choices = c("Any selected code (OR)" = "or", "All selected codes (AND)" = "and"),
                       selected = "or", inline = TRUE),
          radioButtons("ts_entity_col", "Rank by:",
                       choices = c("Client (who's paying)" = "client.name", "Registrant (who's paid)" = "registrant.name"),
                       selected = "client.name"),
          radioButtons("ts_metric", "Metric:", choices = c("expenses", "income"), selected = "expenses", inline = TRUE),
          numericInput("ts_n", "Show top N entities", value = 20, min = 1, max = 200),
          div(actionLink("ts_toggleAdvanced", "Show/Hide additional search fields"), style = "margin-bottom: 0.5em;"),
          shinyjs::hidden(
            div(id = "ts_advanced",
                textInput("ts_issues", "Issues (comma-separated keyword search)", value = ""),
                radioButtons("ts_issues_joiner", "Keyword Joiner:", choices = c("and", "or"), selected = "", inline = TRUE),
                selectInput("ts_years", "Year(s)", choices = 2022:2026, selected = 2026, multiple = TRUE),
                textInput("ts_client_name", "Client Name (one client only)", value = ""),
                textInput("ts_registrant_name", "Registrant Name (one registrant only)", value = ""),
                selectInput("ts_filing_period", "Filing Period",
                            choices = c("", "first_quarter", "second_quarter", "third_quarter", "fourth_quarter")),
                dateInput("ts_starting_date", "Starting Date", value = "2022-01-01", format = "yyyy-mm-dd"),
                dateInput("ts_ending_date", "Ending Date", value = NULL, format = "yyyy-mm-dd"),
                textInput("ts_min_amount", "Minimum Amount (USD)", value = ""),
                textInput("ts_max_amount", "Maximum Amount (USD)", value = ""),
                checkboxInput("ts_ignore_disclaimer", "Ignore Disclaimer", value = FALSE),
                width = 12
            )
          ),
          div(id = "ts_actionbuttons",
              actionButton("ts_query", "Get Top Spenders", class = "btn-primary")
          ),
          br(),
          div(id = "ts_factcheck_box",
              checkboxInput("ts_factcheck", "Enable fact-check view", value = FALSE),
              shinyjs::hidden(
                div(id = "ts_factcheck_help",
                    p(strong("What this does:"), " The ranking to the right is a ", em("sum"),
                      " of every matching filing's spend -- it doesn't show you which specific",
                      " filings produced those numbers. Checking this box shows every individual",
                      " filing matching your search above (not just the top N shown in the ranking),",
                      " one row per filing, with exactly the columns needed to verify a number by",
                      " hand: ", tags$code("registrant.name"), ", ", tags$code("client.name"), ", ",
                      tags$code("filing_type_display"), ", ", tags$code("income"), ", ",
                      tags$code("expenses"), ", ", tags$code("filing_year"), ", ",
                      tags$code("dt_posted"), ", ", tags$code("filing_document_url"), " (a direct",
                      " link to the filing exactly as submitted to the Senate), ",
                      tags$code("registrant.description"), ", ", tags$code("client.general_description"),
                      ", ", tags$code("filing_type"), ", and ", tags$code("filing_period"), " -- plus",
                      " one more column per ALI code selected above, showing that filing's own",
                      " text for that issue (e.g. ", tags$code("Taxation/Internal Revenue Code"),
                      "), so you can see in the filer's own words what it said it was lobbying on."),
                    p(em("Summing this table's income/expenses for any one entity reproduces that",
                         " entity's grand total in the ranking to the right exactly -- verified, not",
                         " assumed."))
                )
              )
          ),
          width = 3
        ),
        mainPanel(
          h4("Top Spenders"),
          verbatimTextOutput("ts_status"),
          DTOutput("ts_entity_totals_table"),
          shinyjs::hidden(
            div(id = "ts_factcheck_panel",
                h4("Fact-check: every raw filing behind this search"),
                DTOutput("ts_raw_filings_table")
            )
          ),
          width = 9
        )
      )
    )
  )
)

####### Define the server logic for the app
server <- function(input, output, session) {
  ####### Create a reactiveValues object to store the main data frame
  rv <- reactiveValues(result_df = NULL, original_df = NULL, display_df = NULL)
  status_message <- reactiveVal("")

  ####### Observe the Query button and handle local-data querying and table rendering
  observeEvent(input$query, {
    showModal(
      modalDialog(
        title = "Loading",
        div(
          tags$h4("Loading filings from the local corpus. First run for a new year can take a few minutes (cached after that)."),
          tags$div(class = "spinner-border", role = "status", style = "margin:10px;"),
          "Please wait."
        ),
        size = "l", easyClose = FALSE, fade = TRUE, footer = NULL
      )
    )
    param_list <- list(
      issues = if (nzchar(input$issues)) unlist(strsplit(input$issues, ",\\s*")) else "",
      issue_joiner = input$issue_joiner,
      years = if (length(input$years) > 0) as.integer(input$years) else "",
      filing_period = if (nzchar(input$filing_period)) input$filing_period else "",
      client_name = if (nzchar(input$client_name)) input$client_name else "",
      registrant_name = if (nzchar(input$registrant_name)) input$registrant_name else "",
      starting_date = if (!is.null(input$starting_date)) format(input$starting_date, "%Y-%m-%d") else "",
      ending_date = if (!is.null(input$ending_date)) format(input$ending_date, "%Y-%m-%d") else "",
      tidy_result = input$tidy_result,
      ignore_disclaimer = input$ignore_disclaimer,
      min_amount = input$min_amount,
      max_amount = input$max_amount
    )
    param_list <- param_list[!sapply(param_list, function(x) is.null(x) || (length(x) > 0 && all(x == "")))]

    output$results <- renderPrint({
      cat(build_call_string(param_list))
    })

    result <- withCallingHandlers(
      tryCatch({
        do.call(get_local_senate_filings, param_list)
      }, error = function(e) {
        return(paste("Error:", conditionMessage(e)))
      }),
      message = function(m) status_message(m$message)
    )

    removeModal()
    output$main_status <- renderText({ status_message() })

    if (is.character(result)) {
      rv$result_df <- NULL
      rv$original_df <- NULL
      rv$display_df <- NULL
    } else {
      rv$result_df <- result
      rv$original_df <- result
      rv$display_df <- result
    }

    output$data_table <- renderDataTable({ render_filings_table(rv$display_df) })
  })

  ##### Flag dupes radio buttons cleaning functionality
  observeEvent(input$dupes_group, {
    req(rv$display_df)
    if (input$dupes_group == "a") {
      rv$display_df <- flag_dupes(rv$display_df, find_duplicates = TRUE, attempt_cleaning = FALSE)
    } else if (input$dupes_group == "b") {
      rv$display_df <- flag_dupes(rv$display_df, find_duplicates = TRUE, attempt_cleaning = TRUE)
    } else if (input$dupes_group == "c") {
      rv$display_df <- rv$original_df
    }
    output$data_table <- renderDataTable({ render_filings_table(rv$display_df) })
  })

  #### flag conflict radio button-related functionality
  observeEvent(input$conflict_group, {
    req(rv$display_df)
    if (input$conflict_group == "a") {
      rv$display_df <- flag_client_registrant_conflict(rv$display_df, flag_conflict = TRUE, clean_doublecounts = FALSE)
    } else if (input$conflict_group == "b") {
      rv$display_df <- flag_client_registrant_conflict(rv$display_df, flag_conflict = TRUE, clean_doublecounts = TRUE)
    } else if (input$conflict_group == "c") {
      rv$display_df <- rv$original_df
    }
    output$data_table <- renderDataTable({ render_filings_table(rv$display_df) })
  })

  ####### Reset all form and helper inputs when the Reset button is clicked
  observeEvent(input$reset, {
    shinyjs::reset("myapp")
    shinyjs::reset("cleaning_helpers")
  })

  observeEvent(input$toggleAdvanced, { shinyjs::toggle(id = "advanced", anim = TRUE) })
  observeEvent(input$toggleconflict, { shinyjs::toggle(id = "conflict", anim = TRUE) })
  observeEvent(input$toggledupes, { shinyjs::toggle(id = "dupes", anim = TRUE) })
  observeEvent(input$toggleMath, { shinyjs::toggle(id = "math_dropdown", anim = TRUE) })

  ####### Math functionality: sum totals and show in a modal dialog
  observeEvent(input$sum_totals, {
    df <- if (!is.null(rv$display_df)) rv$display_df else rv$result_df
    if (is.null(df)) {
      showModal(modalDialog(title = "No Data", "No data available to sum. Please run a query first.", easyClose = TRUE))
      return()
    }
    if ("income" %in% names(df)) df$income <- as.numeric(gsub("[^0-9.-]", "", df$income))
    if ("expenses" %in% names(df)) df$expenses <- as.numeric(gsub("[^0-9.-]", "", df$expenses))
    income_sum <- if ("income" %in% names(df)) sum(df$income, na.rm = TRUE) else NA
    expenses_sum <- if ("expenses" %in% names(df)) sum(df$expenses, na.rm = TRUE) else NA
    income_sum_fmt <- if (!is.na(income_sum)) format(income_sum, big.mark = ",", scientific = FALSE, digits = 2, nsmall = 2) else NA
    expenses_sum_fmt <- if (!is.na(expenses_sum)) format(expenses_sum, big.mark = ",", scientific = FALSE, digits = 2, nsmall = 2) else NA
    msg <- paste0(
      if (!is.na(income_sum_fmt)) sprintf("Total Income: $%s\n", income_sum_fmt) else "",
      if (!is.na(expenses_sum_fmt)) sprintf("Total Expenses: $%s", expenses_sum_fmt) else ""
    )
    showModal(modalDialog(title = "Sum Totals", pre(msg), easyClose = TRUE))
  })

  ####### Download handler for exporting all results as CSV
  output$download_all <- downloadHandler(
    filename = function() paste0("local_lobbying_results_", Sys.Date(), ".csv"),
    content = function(file) {
      if (!is.null(rv$display_df)) {
        write.csv(rv$display_df, file, row.names = FALSE)
      } else {
        write.csv(data.frame(), file)
      }
    }
  )

  ####### Thematic Clusters tab
  enriched_df <- reactive({
    if (!file.exists(ENRICHED_TAX_PATH)) return(NULL)
    readRDS(ENRICHED_TAX_PATH)
  })

  output$cluster_theme_picker <- renderUI({
    df <- enriched_df()
    if (is.null(df)) {
      return(p(strong(
        "No enriched dataset found yet at ", code(ENRICHED_TAX_PATH),
        ". Run skills/lobbying-issue-theme-clustering/scripts/run_pipeline.R first."
      )))
    }
    choices <- sort(unique(df$cluster_lobbying_activity_theme))
    selectInput("cluster_theme", "Lobbying activity theme", choices = choices, selected = choices[1])
  })

  output$cluster_counts_plot <- renderPlot({
    df <- enriched_df()
    req(df)
    counts <- df |>
      dplyr::count(cluster_lobbying_activity_theme, sort = TRUE) |>
      utils::head(15)
    par(mar = c(5, 22, 2, 2))
    barplot(
      rev(counts$n), names.arg = rev(counts$cluster_lobbying_activity_theme),
      horiz = TRUE, las = 1, col = "#FCC780",
      xlab = "Number of filings", main = "Top 15 themes by filing count"
    )
  })

  output$cluster_data_table <- renderDataTable({
    df <- enriched_df()
    req(df, input$cluster_theme)
    sub <- df |>
      dplyr::filter(cluster_lobbying_activity_theme == input$cluster_theme) |>
      dplyr::select(registrant.name, client.name, activity_summary, cluster,
                     cluster_actor_theme, cluster_reasoning, income, expenses)
    render_filings_table(sub)
  })

  ####### Top Spenders by Issue tab
  ts_rv <- reactiveValues(result = NULL)

  observeEvent(input$ts_toggleAdvanced, { shinyjs::toggle(id = "ts_advanced", anim = TRUE) })

  ####### Reveal the fact-check help text + panel together when the checkbox is toggled
  observeEvent(input$ts_factcheck, {
    shinyjs::toggle(id = "ts_factcheck_help", condition = input$ts_factcheck)
    shinyjs::toggle(id = "ts_factcheck_panel", condition = input$ts_factcheck)
  })

  observeEvent(input$ts_query, {
    req(input$ali_codes)
    showModal(
      modalDialog(
        title = "Loading",
        div(
          tags$h4("Loading filings from the local corpus. First run for a new year can take a few minutes (cached after that)."),
          tags$div(class = "spinner-border", role = "status", style = "margin:10px;"),
          "Please wait."
        ),
        size = "l", easyClose = FALSE, fade = TRUE, footer = NULL
      )
    )

    ####### Same param-assembly pattern as the Search Filings tab's query handler, reading
    ####### from this tab's own ts_-prefixed inputs so both tabs' filters stay independent.
    param_list <- list(
      issues = if (nzchar(input$ts_issues)) unlist(strsplit(input$ts_issues, ",\\s*")) else "",
      issue_joiner = input$ts_issues_joiner,
      years = if (length(input$ts_years) > 0) as.integer(input$ts_years) else "",
      filing_period = if (nzchar(input$ts_filing_period)) input$ts_filing_period else "",
      client_name = if (nzchar(input$ts_client_name)) input$ts_client_name else "",
      registrant_name = if (nzchar(input$ts_registrant_name)) input$ts_registrant_name else "",
      starting_date = if (!is.null(input$ts_starting_date)) format(input$ts_starting_date, "%Y-%m-%d") else "",
      ending_date = if (!is.null(input$ts_ending_date)) format(input$ts_ending_date, "%Y-%m-%d") else "",
      tidy_result = FALSE,  # always FALSE here -- ALI-code filtering needs the wide issue columns
      ignore_disclaimer = input$ts_ignore_disclaimer,
      min_amount = input$ts_min_amount,
      max_amount = input$ts_max_amount
    )
    param_list <- param_list[!sapply(param_list, function(x) is.null(x) || (length(x) > 0 && all(x == "")))]

    result <- tryCatch({
      df <- do.call(get_local_senate_filings, param_list)
      cleaned <- df |> flag_dupes() |> flag_client_registrant_conflict()
      top_spenders_by_issue(
        cleaned,
        ali_codes = input$ali_codes,
        issue_joiner = input$ali_issue_joiner,
        entity_col = input$ts_entity_col,
        metric = input$ts_metric,
        n = input$ts_n
      )
    }, error = function(e) paste("Error:", conditionMessage(e)))

    removeModal()

    if (is.character(result)) {
      ts_rv$result <- NULL
      output$ts_status <- renderText(result)
      output$ts_entity_totals_table <- renderDataTable({
        datatable(data.frame(Error = result), rownames = FALSE)
      })
    } else {
      ts_rv$result <- result
      output$ts_status <- renderText(sprintf(
        "Ranked %d entities across %d matching filings.",
        nrow(result$entity_totals), nrow(result$raw_filings)
      ))
      output$ts_entity_totals_table <- renderDataTable({
        dt <- datatable(
          result$entity_totals,
          colnames = c("Entity", "Total Spend"),
          rownames = FALSE,
          options = list(pageLength = -1, dom = "Bfrtip")
        )
        DT::formatCurrency(dt, "grand_total", currency = "$", digits = 0)
      })
    }
  })

  ####### Fact-check: every raw filing matching the current search, narrowed to
  ####### FACT_CHECK_COLS (registrant.name, client.name, filing_type_display, income,
  ####### expenses, filing_year, dt_posted, filing_document_url, registrant.description,
  ####### client.general_description, filing_type, filing_period -- defined once in
  ####### top_spenders_by_issue.R) PLUS one `processed_<issue display name>` column per
  ####### ALI code the user selected above -- the filing's own flattened text for that
  ####### issue, so you can see in the filer's own words what the filing said it was
  ####### lobbying on, not just the metadata. No entity picker -- the full set of
  ####### underlying rows is the fact-check, not a per-entity drill-down. Reuses
  ####### render_filings_table() as-is (already handles filing_document_url -> clickable
  ####### link and income/expenses currency formatting).
  output$ts_raw_filings_table <- renderDataTable({
    req(ts_rv$result)
    processed_cols <- grep("^processed_", names(ts_rv$result$raw_filings), value = TRUE)
    sub <- ts_rv$result$raw_filings |> dplyr::select(dplyr::any_of(c(FACT_CHECK_COLS, processed_cols)))
    render_filings_table(sub)
  })
}

####### Launch the Shiny app with the defined UI and server
shinyApp(ui = ui, server = server)
