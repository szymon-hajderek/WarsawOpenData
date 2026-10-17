# Artifacts

Self-contained HTML pages with results. Open a file in a browser; everything (data, styles, scripts) is inside.
Fonts load from Google Fonts and fall back to system fonts offline.

| Page | What it shows | Rebuild (from `backend/`) |
|---|---|---|
| `bus-detection-simulation.html` | Nearest bus detection (MSE) on 2 minutes of live ZTM data: hit rate by GPS radius, median RMSE, one mini map per line with every simulated rider, results table | `uv run python ../algorithms/simulation/export_viz.py` |

Templates live in `templates/`; a script inlines the data into the `/*__DATA__*/null` slot and writes the page here.
The page texts are in Polish, like the app.
