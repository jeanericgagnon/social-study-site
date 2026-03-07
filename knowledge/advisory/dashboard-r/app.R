suppressPackageStartupMessages({
  library(shiny)
  library(bslib)
  library(DBI)
  library(RSQLite)
  library(dplyr)
  library(tidyr)
  library(lubridate)
  library(ggplot2)
  library(plotly)
  library(scales)
  library(glue)
})

DB_PATH <- normalizePath(file.path("..", "db", "health_advisory.db"), mustWork = FALSE)
TARGET_CROSSING_DATE <- as.Date("2027-07-12")

load_whoop <- function(path) {
  con <- dbConnect(SQLite(), path)
  on.exit(dbDisconnect(con), add = TRUE)
  dbGetQuery(con, "
    SELECT day, recovery_score, sleep_performance, strain
    FROM whoop_daily
    ORDER BY day
  ") %>%
    mutate(day = as.Date(day))
}

load_swim <- function(path) {
  con <- dbConnect(SQLite(), path)
  on.exit(dbDisconnect(con), add = TRUE)
  dbGetQuery(con, "
    SELECT day, distance_value, unit
    FROM swim_daily
    ORDER BY day
  ") %>%
    mutate(
      day = as.Date(day),
      unit = tolower(unit),
      yards = case_when(
        unit %in% c('yd','yard','yards') ~ as.numeric(distance_value),
        unit %in% c('m','meter','meters') ~ as.numeric(distance_value) * 1.09361,
        unit %in% c('mi','mile','miles') ~ as.numeric(distance_value) * 1760,
        TRUE ~ as.numeric(distance_value)
      )
    )
}

range_filter <- function(df, preset) {
  if (!nrow(df)) return(df)
  end <- max(df$day, na.rm = TRUE)
  start <- switch(
    preset,
    "3D" = end - days(2),
    "7D" = end - days(6),
    "14D" = end - days(13),
    "30D" = end - days(29),
    "90D" = end - days(89),
    "ALL" = min(df$day, na.rm = TRUE),
    end - days(29)
  )
  df %>% filter(day >= start, day <= end)
}

ui <- page_navbar(
  title = "Health Dashboard v1",
  theme = bs_theme(version = 5, bg = "#0b1020", fg = "#dbeafe", primary = "#60a5fa"),

  nav_panel(
    "Overview",
    card(
      card_header("Range + Overlay Controls"),
      layout_columns(
        selectInput("overview_range", "Range", choices = c("3D","7D","14D","30D","90D","ALL"), selected = "30D"),
        checkboxGroupInput("overlay_metrics", "Overlay lines (off by default)", choices = c("Recovery" = "recovery", "Sleep" = "sleep"), selected = character(0)),
        checkboxInput("show_mean", "Show strain mean", value = TRUE),
        col_widths = c(5, 5, 2)
      )
    ),
    layout_columns(
      card(card_header("Recovery (latest)"), h2(textOutput("recovery_latest"))),
      card(card_header("Sleep % (latest)"), h2(textOutput("sleep_latest"))),
      card(card_header("Strain (latest)"), h2(textOutput("strain_latest"))),
      col_widths = c(12, 12, 12)
    ),
    card(
      card_header("Daily Strain Bars + Overlays"),
      plotlyOutput("trend_plot", height = "420px")
    )
  ),

  nav_panel(
    "Swim Progress",
    card(
      card_header("Range"),
      selectInput("swim_range", NULL, choices = c("3D","7D","14D","30D","90D","ALL"), selected = "30D")
    ),
    layout_columns(
      card(card_header("Week Swim"), h2(textOutput("swim_week"))),
      card(card_header("Route Progress"), h2(textOutput("swim_progress"))),
      card(card_header("Target Date"), h2(textOutput("target_date"))),
      col_widths = c(12, 12, 12)
    ),
    card(
      card_header("Catalina → Long Beach"),
      plotlyOutput("swim_map", height = "430px")
    )
  ),

  nav_panel(
    "Insights",
    card(
      card_header("Simple callouts"),
      uiOutput("insights")
    )
  )
)

server <- function(input, output, session) {
  whoop_all <- reactivePoll(
    10000, session,
    checkFunc = function() file.info(DB_PATH)$mtime,
    valueFunc = function() load_whoop(DB_PATH)
  )

  swim_all <- reactivePoll(
    10000, session,
    checkFunc = function() file.info(DB_PATH)$mtime,
    valueFunc = function() load_swim(DB_PATH)
  )

  whoop <- reactive(range_filter(whoop_all(), input$overview_range))
  swim <- reactive(range_filter(swim_all(), input$swim_range))

  output$recovery_latest <- renderText({
    d <- whoop(); if (!nrow(d)) return("N/A")
    round(dplyr::last(na.omit(d$recovery_score)), 1)
  })
  output$sleep_latest <- renderText({
    d <- whoop(); if (!nrow(d)) return("N/A")
    paste0(round(dplyr::last(na.omit(d$sleep_performance)), 1), "%")
  })
  output$strain_latest <- renderText({
    d <- whoop(); if (!nrow(d)) return("N/A")
    round(dplyr::last(na.omit(d$strain)), 1)
  })

  output$trend_plot <- renderPlotly({
    d <- whoop() %>%
      filter(!is.na(strain)) %>%
      mutate(
        strain_norm = pmin(1, pmax(0, strain / 20)),
        recovery_norm = pmin(1, pmax(0, recovery_score / 100)),
        sleep_norm = pmin(1, pmax(0, sleep_performance / 100))
      )

    validate(need(nrow(d) > 0, "No data in selected range"))

    p <- ggplot(d, aes(x = day)) +
      geom_col(aes(y = strain_norm), fill = "#f97316", alpha = 0.85, width = 0.8) +
      scale_y_continuous(labels = percent_format(), limits = c(0, 1.05)) +
      theme_minimal(base_size = 13) +
      theme(legend.position = "bottom", axis.title = element_blank())

    if ("recovery" %in% input$overlay_metrics) {
      p <- p + geom_line(aes(y = recovery_norm, color = "Recovery"), linewidth = 1.2)
    }
    if ("sleep" %in% input$overlay_metrics) {
      p <- p + geom_line(aes(y = sleep_norm, color = "Sleep"), linewidth = 1.2)
    }
    if (isTRUE(input$show_mean)) {
      mean_strain <- mean(d$strain_norm, na.rm = TRUE)
      p <- p + geom_hline(yintercept = mean_strain, linetype = "dashed", color = "#a78bfa", linewidth = 1) +
        annotate("text", x = min(d$day, na.rm = TRUE), y = mean_strain + 0.03, label = glue("Mean strain: {round(mean_strain*20,1)}"), color = "#a78bfa", hjust = 0, size = 3.5)
    }

    p <- p + scale_color_manual(values = c(Recovery = "#22c55e", Sleep = "#38bdf8"))

    ggplotly(p) %>%
      layout(dragmode = FALSE) %>%
      config(displayModeBar = FALSE, responsive = TRUE, scrollZoom = FALSE)
  })

  output$swim_week <- renderText({
    d <- swim(); if (!nrow(d)) return("0 yd")
    end <- max(d$day, na.rm = TRUE)
    paste0(comma(round(sum(d$yards[d$day >= end - days(6)], na.rm = TRUE), 0)), " yd")
  })

  output$swim_progress <- renderText({
    d <- swim(); if (!nrow(d)) return("0%")
    pct <- min(1, sum(d$yards, na.rm = TRUE) / (22 * 1760))
    paste0(round(pct * 100, 1), "%")
  })

  output$target_date <- renderText(format(TARGET_CROSSING_DATE, "%b %d, %Y"))

  output$swim_map <- renderPlotly({
    d <- swim()
    pct <- if (nrow(d)) min(1, sum(d$yards, na.rm = TRUE) / (22 * 1760)) else 0

    catalina <- c(lat = 33.3455, lng = -118.3278)
    long_beach <- c(lat = 33.7701, lng = -118.1937)
    prog_lat <- catalina[["lat"]] + (long_beach[["lat"]] - catalina[["lat"]]) * pct
    prog_lng <- catalina[["lng"]] + (long_beach[["lng"]] - catalina[["lng"]]) * pct

    plot_ly(type = "scattergeo", mode = "lines") %>%
      add_trace(
        lon = c(catalina[["lng"]], long_beach[["lng"]]),
        lat = c(catalina[["lat"]], long_beach[["lat"]]),
        line = list(color = "#60a5fa", width = 5),
        name = "Route"
      ) %>%
      add_markers(
        lon = c(catalina[["lng"]], long_beach[["lng"]], prog_lng),
        lat = c(catalina[["lat"]], long_beach[["lat"]], prog_lat),
        marker = list(size = c(9, 9, 13), color = c("#22c55e", "#f97316", "#a78bfa")),
        text = c("Catalina", "Long Beach", glue("Progress {round(pct * 100, 1)}%")),
        hoverinfo = "text"
      ) %>%
      layout(
        paper_bgcolor = "rgba(0,0,0,0)",
        geo = list(
          projection = list(type = "mercator"),
          showland = TRUE, landcolor = "#0f172a", showocean = TRUE, oceancolor = "#020617",
          lataxis = list(range = c(33.28, 33.84)),
          lonaxis = list(range = c(-118.42, -118.10))
        ),
        legend = list(orientation = "h", y = -0.15)
      ) %>%
      layout(dragmode = FALSE) %>%
      config(displayModeBar = FALSE, responsive = TRUE, scrollZoom = FALSE)
  })

  output$insights <- renderUI({
    d <- whoop()
    if (!nrow(d)) return(tags$p("No data in selected range."))

    r <- mean(tail(d$recovery_score, 7), na.rm = TRUE)
    s <- mean(tail(d$sleep_performance, 7), na.rm = TRUE)
    st <- mean(tail(d$strain, 7), na.rm = TRUE)

    tags$ul(
      tags$li(glue("7-day avg Recovery: {round(r,1)}")),
      tags$li(glue("7-day avg Sleep: {round(s,1)}%")),
      tags$li(glue("7-day avg Strain: {round(st,2)}"))
    )
  })
}

shinyApp(ui, server)
