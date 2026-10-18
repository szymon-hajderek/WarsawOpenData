# feature/exclude-modes

- `RouteRequest.excludeModes`: list of `bus` | `tram` | `metro` | `rail` | `veturilo` (default `[]`, other values 422).
- `/plan` gets `exclude_modes`; `veturilo` also sends `veturilo_s: 0`. Own bike (`travel: "bike"`) is not affected.
- Python fallback: `mkuran.departures(..., exclude_modes=())` skips those modes (trolleybus = bus) before the limit.
- Safety net: `_option_clear` drops any option with a leg of an excluded mode.
- Tests: `backend/tests/test_exclude_modes.py`; `data/API.md` updated.
