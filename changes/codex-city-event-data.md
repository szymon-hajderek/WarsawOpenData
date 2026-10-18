# City research event collection

- Collect opt-in searches, selected routes and recording lifecycle actions, including planned legs.
- Reuse 175 m hexes, bucket the explicitly entered calorie age, omit labels, tracks and stable user IDs.
- Attach best-effort availability for Veturilo stations involved in searches/selections, without polling an archive.
- Journal events in private SQLite with retry deduplication; write one atomic JSON per Warsaw day with hourly arrays.
- Recover exports at startup/retry and retain 12 calendar months. Document server storage and backup permissions.
- Introduce a new consent scope, stop frontend legacy counter submissions, retain the legacy API/database.
- Defer issue-reporting UI. Prepare a PR without merging or deploying it.
- Receipt time controls daily/hourly buckets; DST repeated hours share a bucket. Recording finish means an explicit app action.

Validation: 192 backend tests passed; 263 frontend tests passed; ESLint and production build passed. A running local server returned recorded=true and recorded=false on retry for the documented smoke request.
