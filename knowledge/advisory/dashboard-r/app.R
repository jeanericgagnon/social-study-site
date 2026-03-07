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
  if (is.null(preset) || !nzchar(preset)) preset <- "30D"
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
  header = tags$style(HTML("
    .glass-card {
      background: linear-gradient(145deg, rgba(30,41,59,.75), rgba(15,23,42,.55));
      border: 1px solid rgba(148,163,184,.22);
      border-radius: 16px;
      padding: 14px 16px;
      box-shadow: 0 10px 26px rgba(2,6,23,.35);
    }
    .glass-label { color:#93c5fd; font-size:.82rem; text-transform:uppercase; letter-spacing:.08em; }
    .glass-value { font-size:2rem; font-weight:700; line-height:1.1; margin:6px 0; }
    .glass-row { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
    .chip { background: rgba(148,163,184,.18); border:1px solid rgba(148,163,184,.3); border-radius:999px; padding:4px 10px; font-size:.8rem; }
  ")),

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
    p(class = "text-secondary", textOutput("overview_window")),
    uiOutput("overview_hero"),
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
    p(class = "text-secondary", textOutput("swim_window")),
    uiOutput("swim_hero"),
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

  output$overview_window <- renderText({
    d <- whoop()
    if (!nrow(d)) return(glue("Overview range: {input$overview_range} (no data)"))
    glue("Overview range: {input$overview_range} • {min(d$day)} → {max(d$day)} • {nrow(d)} days")
  })

  output$swim_window <- renderText({
    d <- swim()
    if (!nrow(d)) return(glue("Swim range: {input$swim_range} (no data)"))
    glue("Swim range: {input$swim_range} • {min(d$day)} → {max(d$day)} • {nrow(d)} day(s)")
  })

  snapshot_vals <- reactive({
    d <- whoop()
    list(
      recovery = if (!nrow(d)) "N/A" else as.character(round(dplyr::last(na.omit(d$recovery_score)),1)),
      sleep = if (!nrow(d)) "N/A" else paste0(round(dplyr::last(na.omit(d$sleep_performance)),1), "%"),
      strain = if (!nrow(d)) "N/A" else as.character(round(dplyr::last(na.omit(d$strain)),1))
    )
  })

  output$overview_hero <- renderUI({
    v <- snapshot_vals()
    tags$div(class = "glass-card",
      tags$div(class = "glass-label", "Today Snapshot"),
      tags$div(class = "glass-value", glue("Strain {v$strain}")),
      tags$div(class = "glass-row",
        tags$span(class = "chip", glue("Recovery {v$recovery}")),
        tags$span(class = "chip", glue("Sleep {v$sleep}")),
        tags$span(class = "chip", glue("{input$overview_range}"))
      )
    )
  })

  output$swim_hero <- renderUI({
    tags$div(class = "glass-card",
      tags$div(class = "glass-label", "Swim Session"),
      tags$div(class = "glass-value", if (!nrow(swim())) "0 yd" else { end <- max(swim()$day, na.rm = TRUE); paste0(comma(round(sum(swim()$yards[swim()$day >= end - days(6)], na.rm = TRUE),0)), " yd") }),
      tags$div(class = "glass-row",
        tags$span(class = "chip", if (!nrow(swim())) "0%" else paste0(round(min(1, sum(swim()$yards, na.rm = TRUE)/(22*1760))*100,1), "%")),
        tags$span(class = "chip", format(TARGET_CROSSING_DATE, "%b %d, %Y")),
        tags$span(class = "chip", glue("{input$swim_range}"))
      )
    )
  })

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

    if (length(input$overlay_metrics) > 0) {
      p <- p + scale_color_manual(values = c(Recovery = "#22c55e", Sleep = "#38bdf8"))
    }

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
    if (!is.finite(pct)) pct <- 0

    # Catalina Avalon Harbor -> Long Beach shoreline reference
    catalina <- c(lat = 33.3436, lng = -118.3267)
    long_beach <- c(lat = 33.7676, lng = -118.1956)
    prog_lat <- catalina[["lat"]] + (long_beach[["lat"]] - catalina[["lat"]]) * pct
    prog_lng <- catalina[["lng"]] + (long_beach[["lng"]] - catalina[["lng"]]) * pct

    plot_ly() %>%
      add_trace(
        type = "scattermapbox",
        mode = "lines",
        lon = c(catalina[["lng"]], long_beach[["lng"]]),
        lat = c(catalina[["lat"]], long_beach[["lat"]]),
        line = list(color = "#60a5fa", width = 4),
        name = "Catalina → Long Beach",
        hoverinfo = "skip"
      ) %>%
      add_trace(
        type = "scattermapbox",
        mode = "markers+text",
        lon = c(catalina[["lng"]], long_beach[["lng"]], prog_lng),
        lat = c(catalina[["lat"]], long_beach[["lat"]], prog_lat),
        text = c("Avalon, Catalina", "", glue("You ({round(pct*100,1)}%)")),
        textposition = c("top right", "top right", "bottom right"),
        marker = list(size = c(10, 10, 14), color = c("#22c55e", "#f97316", "#a78bfa")),
        hovertemplate = c("Avalon, Catalina<extra></extra>", "Long Beach<extra></extra>", glue("You ({round(pct*100,1)}%)<extra></extra>")),
        showlegend = FALSE
      ) %>%
      layout(
        mapbox = list(
          style = "open-street-map",
          zoom = 8.6,
          center = list(lat = 33.56, lon = -118.26)
        ),
        margin = list(l = 0, r = 0, t = 0, b = 0),
        dragmode = FALSE
      ) %>%
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
