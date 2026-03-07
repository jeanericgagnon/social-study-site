# WHOOP Insight Layers Dashboard (R + Shiny)

A high-visual dashboard for WHOOP metrics stored in:

- `knowledge/advisory/db/health_advisory.db`

## Features

- Layered trend chart (Recovery, Sleep %, Strain scaled, Recovery 7d)
- Correlation view (Sleep vs Recovery, colored by Strain)
- Auto insight callouts
- Live auto-refresh (every 10s)
- Data preview tab

## Run

From this folder:

```bash
Rscript run.R
```

Or directly:

```bash
R -e "shiny::runApp('app.R', host='127.0.0.1', port=3838)"
```

Then open:

- <http://127.0.0.1:3838>

## Packages

Install once:

```r
install.packages(c(
  'shiny','bslib','DBI','RSQLite','dplyr','tidyr','lubridate',
  'ggplot2','plotly','scales','glue','purrr'
))
```
