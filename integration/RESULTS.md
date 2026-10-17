# Integration test results

Engine: `real`. Written by `uv run pytest ../integration` (only the scenarios that ran).

## Synthetic data from GTFS

### Banacha -> Plac Unii with a ZTM alert on the planned line (`alert-banacha-unii`): PASS

| Metric | Value |
|---|---|
| alerted line | 167 |
| options after | 6 |
| options with the line | 4 |
| titles | Veturilo + 167 [Zmiana na trasie, Najszybsza], Veturilo [], 167 [Zmiana na trasie], 172 + 167 [Zmiana na trasie], 172 + 167 [Zmiana na trasie], Pieszo [Najaktywniejsza] |

- [x] no tag before the alert starts
- [x] an option still uses the line after the alert
- [x] every option with the line has the tag
- [x] no option without the line has the tag
