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
  library(purrr)
})

DB_PATH <- normalizePath(
  file.path("..", "db", "health_advisory.db"),
  mustWork = FALSE
)

TARGET_CROSSING_DATE <- as.Date("2027-07-12")

validate_db <- function(path) {
  if (!file.exists(path)) {
    stop(glue("DB not found at: {path}"), call. = FALSE)
  }
}

load_whoop <- function(path) {
  validate_db(path)
  con <- dbConnect(SQLite(), path)
  on.exit(dbDisconnect(con), add = TRUE)

  whoop <- dbGetQuery(con, "
    SELECT day, recovery_score, hrv_rmssd, resting_hr,
           sleep_performance, sleep_efficiency, sleep_consistency,
           strain
    FROM whoop_daily
    ORDER BY day
  ")

  whoop %>%
    mutate(
      day = as.Date(day),
      across(where(is.numeric), as.numeric)
    ) %>%
    arrange(day)
}

load_swim <- function(path) {
  validate_db(path)
  con <- dbConnect(SQLite(), path)
  on.exit(dbDisconnect(con), add = TRUE)

  swim <- dbGetQuery(con, "
    SELECT day, distance_value, unit, source
    FROM swim_daily
    ORDER BY day
  ")

  swim %>%
    mutate(
      day = as.Date(day),
      distance_value = as.numeric(distance_value),
      unit = tolower(unit),
      yards = case_when(
        unit %in% c('yd', 'yard', 'yards') ~ distance_value,
        unit %in% c('m', 'meter', 'meters') ~ distance_value * 1.09361,
        unit %in% c('mi', 'mile', 'miles') ~ distance_value * 1760,
        TRUE ~ distance_value
      ),
      miles = yards / 1760
    )
}

complete_daily <- function(df) {
  if (!nrow(df)) return(df)
  full_dates <- tibble(day = seq(min(df$day), max(df$day), by = "day"))
  full_dates %>%
    left_join(df, by = "day") %>%
    arrange(day)
}

rolling_mean <- function(x, n = 7) {
  stats::filter(x, rep(1 / n, n), sides = 1) %>% as.numeric()
}

insight_cards <- function(df) {
  if (!nrow(df)) return(character())

  clean <- df %>% filter(!is.na(recovery_score) | !is.na(sleep_performance) | !is.na(strain))
  if (!nrow(clean)) return("No enough WHOOP signal yet.")

  latest <- clean %>% arrange(desc(day)) %>% slice(1)
  last7 <- clean %>% filter(day >= max(day, na.rm = TRUE) - days(6))
  prev7 <- clean %>% filter(day < max(day, na.rm = TRUE) - days(6), day >= max(day, na.rm = TRUE) - days(13))

  r7 <- mean(last7$recovery_score, na.rm = TRUE)
  p7 <- mean(prev7$recovery_score, na.rm = TRUE)
  s7 <- mean(last7$sleep_performance, na.rm = TRUE)
  st7 <- mean(last7$strain, na.rm = TRUE)

  notes <- c(
    glue("Latest day: {latest$day} • Recovery {round(latest$recovery_score, 1)} • Sleep {round(latest$sleep_performance, 1)}% • Strain {round(latest$strain, 2)}")
  )

  if (is.finite(r7) && is.finite(p7)) {
    delta <- r7 - p7
    dir <- ifelse(delta >= 0, "up", "down")
    notes <- c(notes, glue("Recovery 7d avg is {dir} {abs(round(delta, 1))} vs prior week ({round(r7, 1)} vs {round(p7, 1)})."))
  }

  if (is.finite(s7) && is.finite(st7)) {
    load_flag <- ifelse(st7 > 13, "high", "moderate")
    notes <- c(notes, glue("Current load looks {load_flag}: strain 7d avg {round(st7, 2)} with sleep perf 7d avg {round(s7, 1)}%."))
  }

  miss_days <- df %>% filter(if_any(-day, is.na)) %>% nrow()
  if (miss_days > 0) notes <- c(notes, glue("Data gaps present: {miss_days} day(s) in-range have partial/missing WHOOP values."))

  notes
}

layered_time_plot <- function(df, focus_metric = "Recovery", show_smooth = TRUE) {
  base <- ggplot(df, aes(day)) +
    theme_minimal(base_size = 13) +
    theme(
      plot.background = element_rect(fill = "transparent", color = NA),
      panel.background = element_rect(fill = "transparent", color = NA),
      panel.grid.minor = element_blank(),
      legend.position = "bottom",
      axis.title = element_blank()
    )

  focus_alpha <- function(name) ifelse(focus_metric == name, 1, 0.45)

  p <- base +
    geom_area(aes(y = sleep_performance / 100, fill = "Sleep %"), alpha = 0.20 * focus_alpha("Sleep")) +
    geom_line(aes(y = sleep_performance / 100, color = "Sleep %"), linewidth = 1.0, alpha = focus_alpha("Sleep")) +
    geom_line(aes(y = recovery_score / 100, color = "Recovery"), linewidth = 1.2, alpha = focus_alpha("Recovery")) +
    geom_line(aes(y = strain / 20, color = "Strain (scaled)"), linewidth = 1.0, linetype = "22", alpha = focus_alpha("Strain")) +
    scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, 1.05)) +
    scale_fill_manual(values = c("Sleep %" = "#60a5fa")) +
    scale_color_manual(values = c(
      "Sleep %" = "#38bdf8",
      "Recovery" = "#22c55e",
      "Strain (scaled)" = "#f97316",
      "Recovery 7d" = "#a78bfa"
    ))

  if (isTRUE(show_smooth)) {
    p <- p + geom_line(aes(y = rolling_mean(recovery_score / 100, 7), color = "Recovery 7d"), linewidth = 1.5)
  }

  ggplotly(p, tooltip = c("x", "y", "colour")) %>%
    layout(
      paper_bgcolor = "rgba(0,0,0,0)",
      plot_bgcolor = "rgba(0,0,0,0)",
      legend = list(orientation = "h", y = -0.2)
    )
}

cor_plot <- function(df) {
  clean <- df %>% filter(!is.na(sleep_performance), !is.na(recovery_score), !is.na(strain))
  p <- ggplot(clean, aes(sleep_performance, recovery_score, color = strain)) +
    geom_point(size = 3, alpha = 0.9) +
    geom_smooth(method = "lm", se = FALSE, color = "#a78bfa", linewidth = 1.2) +
    scale_color_viridis_c(option = "C") +
    labs(x = "Sleep Performance %", y = "Recovery Score", color = "Strain") +
    theme_minimal(base_size = 13)

  ggplotly(p, tooltip = c("x", "y", "color"))
}

metric_tiles <- function(df) {
  clean <- df %>% filter(!is.na(recovery_score) | !is.na(sleep_performance) | !is.na(strain))
  latest <- clean %>% slice_tail(n = 1)
  last7 <- clean %>% filter(day >= max(day, na.rm = TRUE) - days(6))

  list(
    recovery_latest = round(latest$recovery_score, 1),
    recovery_7d = round(mean(last7$recovery_score, na.rm = TRUE), 1),
    sleep_latest = round(latest$sleep_performance, 1),
    strain_7d = round(mean(last7$strain, na.rm = TRUE), 2),
    span = glue("{min(clean$day)} → {max(clean$day)}")
  )
}

readiness_score <- function(df) {
  clean <- df %>% filter(!is.na(recovery_score), !is.na(sleep_performance), !is.na(strain))
  if (!nrow(clean)) return(NA_real_)
  latest <- clean %>% slice_tail(n = 1)

  # Weighted composite (0-100): recovery + sleep quality - strain pressure
  score <- 0.55 * latest$recovery_score +
    0.30 * latest$sleep_performance +
    0.15 * pmax(0, 100 - (latest$strain * 5))

  pmax(0, pmin(100, round(score, 1)))
}

anomaly_table <- function(df) {
  clean <- df %>%
    arrange(day) %>%
    mutate(
      rec_z = as.numeric(scale(recovery_score)),
      sleep_z = as.numeric(scale(sleep_performance)),
      strain_z = as.numeric(scale(strain))
    ) %>%
    mutate(
      anomaly = if_else(
        abs(rec_z) > 1.5 | abs(sleep_z) > 1.5 | abs(strain_z) > 1.5,
        TRUE,
        FALSE,
        missing = FALSE
      )
    )

  clean %>%
    filter(anomaly) %>%
    transmute(
      day,
      recovery = round(recovery_score, 1),
      sleep = round(sleep_performance, 1),
      strain = round(strain, 2),
      trigger = case_when(
        abs(rec_z) > 1.5 ~ "Recovery outlier",
        abs(sleep_z) > 1.5 ~ "Sleep outlier",
        abs(strain_z) > 1.5 ~ "Strain outlier",
        TRUE ~ "Mixed"
      )
    ) %>%
    arrange(desc(day))
}

coach_cards <- function(df) {
  clean <- df %>% filter(!is.na(recovery_score), !is.na(sleep_performance), !is.na(strain))
  if (!nrow(clean)) return(c("Not enough data yet for coaching cards."))

  last3 <- clean %>% slice_tail(n = 3)
  rec3 <- mean(last3$recovery_score, na.rm = TRUE)
  slp3 <- mean(last3$sleep_performance, na.rm = TRUE)
  str3 <- mean(last3$strain, na.rm = TRUE)

  cards <- c()
  cards <- c(cards, glue("3-day readiness profile: Recovery {round(rec3, 1)}, Sleep {round(slp3, 1)}%, Strain {round(str3, 2)}."))

  cards <- c(cards, if (rec3 < 55 && str3 > 12) {
    "Dial intensity down 10-20% tomorrow. Keep movement, cut top-end efforts."
  } else if (rec3 > 75 && slp3 > 85) {
    "Good window to push quality work — green-light for a harder session."
  } else {
    "Stay steady: maintain current volume and prioritize consistency over spikes."
  })

  cards <- c(cards, if (slp3 < 80) {
    "Sleep consistency drift detected. Prioritize bedtime stability tonight for recovery lift."
  } else {
    "Sleep signal is supportive — keep pre-sleep routine unchanged."
  })

  cards
}

weekly_narrative <- function(df) {
  clean <- df %>% filter(!is.na(recovery_score), !is.na(sleep_performance), !is.na(strain))
  if (nrow(clean) < 10) return("Collect a bit more data and I’ll generate a stronger weekly narrative.")

  latest_day <- max(clean$day, na.rm = TRUE)
  wk <- clean %>% filter(day >= latest_day - days(6))
  prev <- clean %>% filter(day < latest_day - days(6), day >= latest_day - days(13))

  rec_delta <- mean(wk$recovery_score, na.rm = TRUE) - mean(prev$recovery_score, na.rm = TRUE)
  slp_delta <- mean(wk$sleep_performance, na.rm = TRUE) - mean(prev$sleep_performance, na.rm = TRUE)
  str_delta <- mean(wk$strain, na.rm = TRUE) - mean(prev$strain, na.rm = TRUE)

  glue(
    "This week, recovery is {ifelse(rec_delta >= 0, 'up', 'down')} {abs(round(rec_delta,1))} points, ",
    "sleep performance is {ifelse(slp_delta >= 0, 'up', 'down')} {abs(round(slp_delta,1))} points, and ",
    "strain is {ifelse(str_delta >= 0, 'up', 'down')} {abs(round(str_delta,2))}. ",
    "Interpretation: {ifelse(rec_delta >= 0 && slp_delta >= 0, 'adaptation is trending positive — keep pressure measured.', 'fatigue pressure may be outrunning recovery — bias toward consistency and sleep quality this week.')}"
  )
}

swim_overlay_metrics <- function(swim_df) {
  if (!nrow(swim_df)) {
    return(list(today_yards = 0, week_yards = 0, total_yards = 0, route_progress = 0))
  }

  today <- max(swim_df$day, na.rm = TRUE)
  today_yards <- swim_df %>% filter(day == today) %>% summarise(v = sum(yards, na.rm = TRUE)) %>% pull(v)
  week_yards <- swim_df %>% filter(day >= today - days(6)) %>% summarise(v = sum(yards, na.rm = TRUE)) %>% pull(v)
  total_yards <- sum(swim_df$yards, na.rm = TRUE)

  # Catalina (Avalon) to Long Beach route proxy (~22 miles)
  route_yards <- 22 * 1760
  route_progress <- pmin(1, total_yards / route_yards)

  list(
    today_yards = round(today_yards, 0),
    week_yards = round(week_yards, 0),
    total_yards = round(total_yards, 0),
    route_progress = route_progress
  )
}

ui <- page_navbar(
  title = div(icon("chart-line"), " WHOOP x R Insight Layers"),
  theme = bs_theme(
    version = 5,
    bg = "#0b1020",
    fg = "#dbeafe",
    primary = "#60a5fa",
    secondary = "#a78bfa",
    success = "#22c55e",
    base_font = font_google("Inter")
  ),
  header = tagList(
    tags$style(HTML("\n      .card {\n        background: linear-gradient(135deg, rgba(30,41,59,.55), rgba(15,23,42,.45)) !important;\n        border: 1px solid rgba(148,163,184,.20) !important;\n        backdrop-filter: blur(10px);\n        box-shadow: 0 8px 30px rgba(2, 6, 23, .35);\n      }\n      .card-header {\n        font-weight: 700;\n        letter-spacing: .2px;\n      }\n      .pulse {\n        animation: pulseGlow 2.4s ease-in-out infinite;\n      }\n      @keyframes pulseGlow {\n        0%, 100% { text-shadow: 0 0 0 rgba(96,165,250,.0); }\n        50% { text-shadow: 0 0 14px rgba(96,165,250,.45); }\n      }\n      .narrative-box {\n        padding: 14px 16px;\n        border-radius: 12px;\n        background: rgba(15,23,42,.55);\n        border: 1px solid rgba(96,165,250,.25);\n        line-height: 1.45;\n      }\n      @media (max-width: 768px) {\n        .navbar .nav-link { padding: 12px 14px; font-size: 16px; }\n        .card { border-radius: 14px; }\n        .card-body { padding: 14px !important; }\n        h1, h2 { font-size: 1.4rem !important; }\n        .form-control, .form-select, .selectize-input, .btn {\n          min-height: 46px;\n          font-size: 16px !important;\n        }\n        .plotly.html-widget { min-height: 340px !important; }\n      }\n    "))
  ),

  nav_panel(
    "Dashboard",
    card(
      card_header("Mobile Controls"),
      layout_columns(
        dateRangeInput("date_window", "Date range", start = Sys.Date() - 30, end = Sys.Date()),
        selectizeInput("focus_metric", "Focus metric", choices = c("Recovery", "Sleep", "Strain"), selected = "Recovery"),
        checkboxInput("show_smooth", "Show 7-day smoothing", value = TRUE),
        radioButtons("date_preset", "Quick range", choices = c("3D","7D","14D","30D","90D","ALL","CUSTOM"), selected = "30D", inline = TRUE),
        col_widths = c(12, 12, 12, 12)
      )
    ),
    layout_columns(
      card(
        card_header("Recovery (latest)"),
        h2(textOutput("recovery_latest"), class = "m-0")
      ),
      card(
        card_header("Recovery 7d avg"),
        h2(textOutput("recovery_7d"), class = "m-0")
      ),
      card(
        card_header("Sleep % (latest)"),
        h2(textOutput("sleep_latest"), class = "m-0")
      ),
      card(
        card_header("Strain 7d avg"),
        h2(textOutput("strain_7d"), class = "m-0")
      ),
      col_widths = c(12, 12, 12, 12)
    ),

    card(
      card_header("Layered Trend Engine"),
      card_body(
        p(class = "text-secondary", "Overlay: Sleep %, Recovery, Strain (scaled), Recovery 7d smoothing"),
        plotlyOutput("layered_plot", height = "450px")
      )
    ),

    layout_columns(
      card(
        card_header("Sleep vs Recovery vs Strain"),
        plotlyOutput("cor_plot", height = "360px")
      ),
      card(
        card_header("Auto Insight Callouts"),
        uiOutput("insights")
      ),
      col_widths = c(12, 12)
    )
  ),

  nav_panel(
    "Executive Insights",
    layout_columns(
      card(
        card_header("Readiness Score"),
        h1(textOutput("readiness_score"), class = "m-0 pulse"),
        p(class = "text-secondary", "Composite of Recovery + Sleep - Strain pressure")
      ),
      card(
        card_header("Anomaly Count"),
        h1(textOutput("anomaly_count"), class = "m-0"),
        p(class = "text-secondary", "Days flagged as statistically unusual")
      ),
      col_widths = c(12, 12)
    ),
    layout_columns(
      card(
        card_header("Anomaly Timeline"),
        tableOutput("anomaly_table")
      ),
      card(
        card_header("Weekly Coaching Cards"),
        uiOutput("coach_cards")
      ),
      col_widths = c(12, 12)
    ),
    card(
      card_header("What Changed This Week"),
      div(class = "narrative-box", textOutput("weekly_narrative"))
    )
  ),

  nav_panel(
    "Swim Overlays",
    card(
      card_header("Swim Filters"),
      dateRangeInput("swim_date_window", "Swim date range", start = Sys.Date() - 30, end = Sys.Date()),
      radioButtons("swim_date_preset", "Quick range", choices = c("3D","7D","14D","30D","90D","ALL","CUSTOM"), selected = "30D", inline = TRUE)
    ),
    layout_columns(
      card(
        card_header("Today Swim"),
        h2(textOutput("swim_today"), class = "m-0")
      ),
      card(
        card_header("This Week Swim"),
        h2(textOutput("swim_week"), class = "m-0")
      ),
      card(
        card_header("Projected Crossing Date"),
        h2(textOutput("projected_date"), class = "m-0"),
        p(class = "text-secondary", "Pinned target date (manual override)")
      ),
      card(
        card_header("Catalina Route Progress"),
        h2(textOutput("swim_progress"), class = "m-0"),
        p(class = "text-secondary", "Cumulative swim distance mapped against Catalina → Long Beach reference line")
      ),
      col_widths = c(12, 12, 12, 12)
    ),
    card(
      card_header("Catalina → Long Beach Swim Map"),
      plotlyOutput("swim_map", height = "520px")
    )
  ),

  nav_panel(
    "Data",
    card(
      card_header("Data Window"),
      textOutput("data_span")
    ),
    card(
      card_header("Raw Preview"),
      tableOutput("preview")
    )
  )
)

server <- function(input, output, session) {
  raw <- reactivePoll(
    intervalMillis = 10000,
    session = session,
    checkFunc = function() file.info(DB_PATH)$mtime,
    valueFunc = function() {
      whoop <- load_whoop(DB_PATH)
      complete_daily(whoop)
    }
  )

  swim <- reactivePoll(
    intervalMillis = 10000,
    session = session,
    checkFunc = function() file.info(DB_PATH)$mtime,
    valueFunc = function() {
      load_swim(DB_PATH)
    }
  )

  apply_preset <- function(preset, data_min, data_max) {
    end <- as.Date(Sys.Date())
    if (!is.null(data_max) && !is.na(data_max)) end <- min(end, as.Date(data_max))
    start <- switch(preset,
      "3D" = end - days(2),
      "7D" = end - days(6),
      "14D" = end - days(13),
      "30D" = end - days(29),
      "90D" = end - days(89),
      "ALL" = as.Date(data_min),
      "CUSTOM" = NULL,
      end - days(29)
    )
    if (is.null(start)) return(NULL)
    c(max(as.Date(data_min), start), as.Date(data_max))
  }

  observeEvent(input$date_preset, {
    r <- raw()
    req(nrow(r) > 0)
    rg <- apply_preset(input$date_preset, min(r$day, na.rm = TRUE), max(r$day, na.rm = TRUE))
    if (!is.null(rg)) updateDateRangeInput(session, "date_window", start = rg[1], end = rg[2])
  }, ignoreInit = FALSE)

  observeEvent(input$swim_date_preset, {
    r <- swim()
    req(nrow(r) > 0)
    rg <- apply_preset(input$swim_date_preset, min(r$day, na.rm = TRUE), max(r$day, na.rm = TRUE))
    if (!is.null(rg)) updateDateRangeInput(session, "swim_date_window", start = rg[1], end = rg[2])
  }, ignoreInit = FALSE)

  filtered_raw <- reactive({
    req(input$date_window)
    raw() %>%
      filter(day >= as.Date(input$date_window[1]), day <= as.Date(input$date_window[2]))
  })

  filtered_swim <- reactive({
    req(input$swim_date_window)
    swim() %>%
      filter(day >= as.Date(input$swim_date_window[1]), day <= as.Date(input$swim_date_window[2]))
  })

  tiles <- reactive({
    d <- filtered_raw()
    if (nrow(d) == 0) return(list(recovery_latest = "N/A", recovery_7d = "N/A", sleep_latest = "N/A", strain_7d = "N/A", span = "No data in selected range"))
    metric_tiles(d)
  })
  swim_metrics <- reactive(swim_overlay_metrics(filtered_swim()))

  output$recovery_latest <- renderText(glue("{tiles()$recovery_latest}"))
  output$recovery_7d <- renderText(glue("{tiles()$recovery_7d}"))
  output$sleep_latest <- renderText(glue("{tiles()$sleep_latest}%"))
  output$strain_7d <- renderText(glue("{tiles()$strain_7d}"))
  output$data_span <- renderText(tiles()$span)

  output$layered_plot <- renderPlotly({
    d <- filtered_raw()
    validate(need(nrow(d) > 0, "No data in selected range"))
    layered_time_plot(d, focus_metric = input$focus_metric, show_smooth = input$show_smooth) %>%
      config(displayModeBar = FALSE, responsive = TRUE)
  })
  output$cor_plot <- renderPlotly({
    d <- filtered_raw()
    validate(need(nrow(d) > 2, "Need more data points for correlation"))
    cor_plot(d) %>% config(displayModeBar = FALSE, responsive = TRUE)
  })

  output$insights <- renderUI({
    tags$ul(
      lapply(insight_cards(filtered_raw()), function(x) tags$li(style = "margin-bottom:10px;", x))
    )
  })

  output$readiness_score <- renderText({
    v <- readiness_score(filtered_raw())
    ifelse(is.na(v), "N/A", v)
  })

  output$anomaly_table <- renderTable({
    anomaly_table(filtered_raw()) %>% head(15)
  })

  output$anomaly_count <- renderText({
    nrow(anomaly_table(filtered_raw()))
  })

  output$coach_cards <- renderUI({
    tags$ul(
      lapply(coach_cards(filtered_raw()), function(x) tags$li(style = "margin-bottom:10px;", x))
    )
  })

  output$weekly_narrative <- renderText({
    weekly_narrative(filtered_raw())
  })

  output$swim_today <- renderText(glue("{comma(swim_metrics()$today_yards)} yd"))
  output$swim_week <- renderText(glue("{comma(swim_metrics()$week_yards)} yd"))
  output$projected_date <- renderText(format(TARGET_CROSSING_DATE, "%B %d, %Y"))
  output$swim_progress <- renderText(glue("{round(swim_metrics()$route_progress * 100, 1)}%"))

  output$swim_map <- renderPlotly({
    catalina <- c(lat = 33.3455, lng = -118.3278)
    long_beach <- c(lat = 33.7701, lng = -118.1937)

    p <- swim_metrics()$route_progress
    if (!is.finite(p)) p <- 0
    prog_lat <- catalina[["lat"]] + (long_beach[["lat"]] - catalina[["lat"]]) * p
    prog_lng <- catalina[["lng"]] + (long_beach[["lng"]] - catalina[["lng"]]) * p

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
        marker = list(size = c(10, 10, 14), color = c("#22c55e", "#f97316", "#a78bfa")),
        text = c("Catalina", "Long Beach", glue("Progress {round(p*100,1)}%")),
        hoverinfo = "text",
        name = "Points"
      ) %>%
      layout(
        paper_bgcolor = "rgba(0,0,0,0)",
        geo = list(
          projection = list(type = "mercator"),
          showcountries = FALSE,
          showland = TRUE,
          landcolor = "#0f172a",
          showocean = TRUE,
          oceancolor = "#020617",
          bgcolor = "rgba(0,0,0,0)",
          lataxis = list(range = c(min(catalina[["lat"]], long_beach[["lat"]]) - 0.05, max(catalina[["lat"]], long_beach[["lat"]]) + 0.05)),
          lonaxis = list(range = c(min(catalina[["lng"]], long_beach[["lng"]]) - 0.10, max(catalina[["lng"]], long_beach[["lng"]]) + 0.10))
        ),
        legend = list(orientation = "h", y = -0.15)
      ) %>%
      config(displayModeBar = FALSE, responsive = TRUE)
  })

  output$preview <- renderTable({
    filtered_raw() %>%
      mutate(across(where(is.numeric), ~ round(.x, 2))) %>%
      tail(20)
  })
}

shinyApp(ui, server)
