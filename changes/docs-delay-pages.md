# docs/delay-pages

Tidy `artifacts/`: one folder per topic, the delay feature as two pages plus a test log.

- `artifacts/delays/`: `delay-statistics.html` (was `delay-simulation.html`, rebuilt on current main from
  `data/live/delay_sample.json.gz`, same numbers; template got a test summary), `delay-docs.html` (new: merges the
  removed `delays-report.html` and `bus-delay-ui-guide.html`), `tests/delay-tests.html` (new: what was tested, on what
  data, results, how to repeat), `templates/delay-statistics.html`.
- `artifacts/bus-detection/` and `artifacts/veturilo-siting/`: pages and templates moved, content unchanged.
- Paths updated in `export_delay_viz.py`, `export_viz.py`, `siting_report.py`, `data/SITING_REPORT.md`, `README.md`,
  `AGENTS.md`, `artifacts/README.md` (folder tree, rule: no loose pages in `artifacts/`).
- All files moved were added by the same author (git history); no code or API changes.
