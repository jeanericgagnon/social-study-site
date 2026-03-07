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

layered_time_plot <- function(df) {
  base <- ggplot(df, aes(day)) +
    theme_minimal(base_size = 13) +
    theme(
      plot.background = element_rect(fill = "transparent", color = NA),
      panel.background = element_rect(fill = "transparent", color = NA),
      panel.grid.minor = element_blank(),
      legend.position = "bottom",
      axis.title = element_blank()
    )

  p <- base +
    geom_area(aes(y = sleep_performance / 100, fill = "Sleep %"), alpha = 0.20) +
    geom_line(aes(y = sleep_performance / 100, color = "Sleep %"), linewidth = 1.0) +
    geom_line(aes(y = recovery_score / 100, color = "Recovery"), linewidth = 1.2) +
    geom_line(aes(y = strain / 20, color = "Strain (scaled)"), linewidth = 1.0, linetype = "22") +
    geom_line(aes(y = rolling_mean(recovery_score / 100, 7), color = "Recovery 7d"), linewidth = 1.5) +
    scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, 1.05)) +
    scale_fill_manual(values = c("Sleep %" = "#60a5fa")) +
    scale_color_manual(values = c(
      "Sleep %" = "#38bdf8",
      "Recovery" = "#22c55e",
      "Strain (scaled)" = "#f97316",
      "Recovery 7d" = "#a78bfa"
    ))

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

  nav_panel(
    "Dashboard",
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
      col_widths = c(3, 3, 3, 3)
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
      col_widths = c(8, 4)
    )
  ),

  nav_panel(
    "Executive Insights",
    layout_columns(
      card(
        card_header("Readiness Score"),
        h1(textOutput("readiness_score"), class = "m-0"),
        p(class = "text-secondary", "Composite of Recovery + Sleep - Strain pressure")
      ),
      card(
        card_header("Anomaly Count"),
        h1(textOutput("anomaly_count"), class = "m-0"),
        p(class = "text-secondary", "Days flagged as statistically unusual")
      ),
      col_widths = c(6, 6)
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
      col_widths = c(7, 5)
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

  tiles <- reactive(metric_tiles(raw()))

  output$recovery_latest <- renderText(glue("{tiles()$recovery_latest}"))
  output$recovery_7d <- renderText(glue("{tiles()$recovery_7d}"))
  output$sleep_latest <- renderText(glue("{tiles()$sleep_latest}%"))
  output$strain_7d <- renderText(glue("{tiles()$strain_7d}"))
  output$data_span <- renderText(tiles()$span)

  output$layered_plot <- renderPlotly(layered_time_plot(raw()))
  output$cor_plot <- renderPlotly(cor_plot(raw()))

  output$insights <- renderUI({
    tags$ul(
      lapply(insight_cards(raw()), function(x) tags$li(style = "margin-bottom:10px;", x))
    )
  })

  output$readiness_score <- renderText({
    v <- readiness_score(raw())
    ifelse(is.na(v), "N/A", v)
  })

  output$anomaly_table <- renderTable({
    anomaly_table(raw()) %>% head(15)
  })

  output$anomaly_count <- renderText({
    nrow(anomaly_table(raw()))
  })

  output$coach_cards <- renderUI({
    tags$ul(
      lapply(coach_cards(raw()), function(x) tags$li(style = "margin-bottom:10px;", x))
    )
  })

  output$preview <- renderTable({
    raw() %>%
      mutate(across(where(is.numeric), ~ round(.x, 2))) %>%
      tail(20)
  })
}

shinyApp(ui, server)
