# docs/street-routing-report-only

- `AGENTS.md`: new rule "Street routing and the route engine: report only". The street routing code (`osm.py`,
  `street_model.py`, `street_graph.py`, `algorithms/router/`, `preprocess_street.py`) and the route engine
  (`backend/app/routing/`, `algorithms/plan_trip.py`, `algorithms/lateness.py`) have their own maintainers: agents do
  not change them, they open a GitHub issue and tell the user.
- No code change.
