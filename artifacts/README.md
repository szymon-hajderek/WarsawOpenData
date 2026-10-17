# Artifacts

Self-contained HTML pages with results. Open a file in a browser; everything (data, styles, scripts) is inside.
Fonts load from Google Fonts and fall back to system fonts offline.

| Page | What it shows | Rebuild (from `backend/`) |
|---|---|---|
| `bus-detection-fraction.html` | The same test with each point placed at u·L (u ~ U(0, 1), 10 points per line): results, hit rate by u, how time is handled, complexity with a runtime benchmark | same command (writes both pages) |
| `delay-simulation.html` | Delay estimate (`algorithms/bus_delay.py`) on 30 min of live data recorded on a local server: availability, error vs the full-track reference, robustness (lost polls, GPS noise), one vehicle stop by stop, maps and tables per line and stop, live server answers | `uv run python ../algorithms/simulation/export_delay_viz.py` (sample: `record_delay_sample.py`) |
| `veturilo-siting.html` | Where to put new Veturilo stations: hex grid (175 m) with the J_synergy cost, layers T / E / S / d_net / J, mock traffic counters and e-scooter events, greedy picks step by step with a slider, top-10 table. T and E are mock data | `uv run python siting_report.py` |
| `bus-detection-simulation.html` | Nearest bus detection (MSE) on 2 minutes of live ZTM data: hit rate by GPS radius, median RMSE, one mini map per line with every simulated rider, results table, how time is handled, complexity | `uv run python ../algorithms/simulation/export_viz.py` |

Templates live in `templates/`; a script inlines the data into the `/*__DATA__*/null` slot and writes the page here.
The page texts are in Polish, like the app.
