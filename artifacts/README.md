# Artifacts

Self-contained HTML pages with results. Open a file in a browser; everything (data, styles, scripts) is inside.
Fonts load from Google Fonts and fall back to system fonts offline. The page texts are in Polish, like the app.

One folder per topic. A page built by a script has its template in that folder's `templates/`: the script inlines the
data into the `/*__DATA__*/null` slot and writes the page next to it. Do not put loose pages in `artifacts/` itself.

```
artifacts/
├── delays/                      live bus / tram delays
│   ├── delay-docs.html          documentation of the feature
│   ├── delay-statistics.html    statistics (built)
│   ├── templates/delay-statistics.html, templates/radius-search.html
│   └── tests/
│       ├── delay-tests.html     what was tested, on what data, results, how to repeat
│       └── radius-search.html   search for the best radius R (built)
├── bus-detection/               "which vehicle am I in?"
│   ├── bus-detection-simulation.html
│   ├── bus-detection-fraction.html
│   └── templates/bus-detection-simulation.html
└── veturilo-siting/             where to put new Veturilo stations
    ├── veturilo-siting.html
    └── templates/veturilo-siting.html
```

| Page | What it shows | Rebuild (from `backend/`) |
|---|---|---|
| `delays/delay-docs.html` | How the delay estimate works on the server, where the app shows it (route list), the API, the `bus-delay` event with a ready React hook for UI work, limits and open follow-ups, files | none, edited by hand |
| `delays/delay-statistics.html` | Delay estimate on the 32-minute recording of 2026-10-17: availability, error vs the full-track reference, robustness (lost polls, GPS noise), radius search, maps and tables per line and stop, live server answers, test summary | `uv run python ../algorithms/simulation/export_delay_viz.py` (sample: `record_delay_sample.py`) |
| `delays/tests/delay-tests.html` | Test log of the delay feature: unit tests one by one, backend and frontend suites, live tuning, simulation, radius search, live endpoint checks, the route list in the running app, what could not be tested | none, edited by hand |
| `delays/tests/radius-search.html` | Two-step search for the best radius R on the 2026-10-17 recording (20–200 m every 10 m, then every 1 m between the two best neighbours): chart of score and availability, full tables, why the curve goes flat, the pick (80 m, now the default) | `uv run python ../algorithms/simulation/search_delay_radius.py --report` |
| `bus-detection/bus-detection-simulation.html` | Nearest bus detection (MSE) on 2 minutes of live ZTM data: hit rate by GPS radius, median RMSE, one mini map per line with every simulated rider, results table, how time is handled, complexity | `uv run python ../algorithms/simulation/export_viz.py` |
| `bus-detection/bus-detection-fraction.html` | The same test with each point placed at u·L (u ~ U(0, 1), 10 points per line): results, hit rate by u, how time is handled, complexity with a runtime benchmark | the same `export_viz.py` (writes both pages) |
| `veturilo-siting/veturilo-siting.html` | Where to put new Veturilo stations: hex grid (175 m) with the J_synergy cost, layers T / E / S / d_net / J, mock traffic counters and e-scooter events, greedy picks step by step with a slider, top-10 table; canvas map without base tiles. T and E are mock data | `uv run python siting_report.py` |
