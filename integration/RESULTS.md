# Integration test results

Engine: `real`. Written by `uv run pytest ../integration` (only the scenarios that ran).

## Recorded live data

### Which bus am I on? (2-minute recording) (`recorded-bus-ride`): PASS

| Metric | Value |
|---|---|
| users | 30 |
| GPS error (m) | 10/30/50 |
| requests with 3 fixes | 264 |
| top-4 with 3 fixes (%) | 99.6 |
| top-1 with 3 fixes (%) | 80.7 |
| top-1 with 1 fix (%) | 66.7 |

- [x] the replayed feed has the recorded buses at every step (> 800)
- [x] own bus in the top 4 for at least 98% of requests with 3 fixes
- [x] own bus first for at least 75% of requests with 3 fixes
- [x] /api/live/delay answers for a ridden bus

## Synthetic data from GTFS

### Banacha -> Plac Unii with a ZTM alert on the planned line (`alert-banacha-unii`): PASS

| Metric | Value |
|---|---|
| alerted line | 167 |
| options after | 6 |
| options with the line | 3 |
| titles | Veturilo + 167 [Zmiana na trasie, Najszybsza], 167 [Zmiana na trasie], Veturilo [Najaktywniejsza], 172 + 167 [Zmiana na trasie], Pieszo [], 136 + 138 [] |

- [x] no tag before the alert starts
- [x] an option still uses the line after the alert
- [x] every option with the line has the tag
- [x] no option without the line has the tag

### Plac Zbawiciela -> Wilanowska with the tram 4 min late (`delay-zbawiciela-wilanowska`): PASS

| Metric | Value |
|---|---|
| option | 10 |
| delayed vehicle | line 10, brigade 4 |
| set delay (s) | 240 |
| plan before | 08:32-09:00 |
| plan after | 08:35-09:03 |
| arrival shift (s) | 180.0 |
| arrival vs new plan (s, + = late) | -45.0 |
| tags after | opóźnienie 3 min |

- [x] arrival moves by the delay (240 s +- 90 s)
- [x] the option has the tag 'opóźnienie N min' with N = 4 +- 1
- [x] the option had no delay tag before
- [x] travel finished (ok)
- [x] the user leaving at the new time arrives no later than the new plan + 3 min

### Route engine: options leave soon after the query (`engine-sanity`): PASS, 3 known bugs

| Metric | Value |
|---|---|
| pkin-galeria-mokotow | 4 options at 08:00; late: - |
| zbawiciela-wilanowska | 5 options at 08:30; late: - |
| banacha-unii | 6 options at 12:00; late: - |
| dworzec-wschodni-zamek | 6 options at 08:30; late: N71 00:40, N02 + N21 23:40, N03 + N21 00:06, 13 13:56 |
| unii-wilanow | 4 options at 08:30; late: N37 + N31 00:22 |
| politechnika-wilanow | 0 options at 12:02; late: - |

- [x] pkin-galeria-mokotow: no late options and at least one option
- [x] zbawiciela-wilanowska: no late options and at least one option
- [x] banacha-unii: no late options and at least one option
- [ ] dworzec-wschodni-zamek: no late options and at least one option (known bug: night buses (N71 at 00:40, N02 at 23:40) and a tram at 13:56 for an 08:30 query)
- [ ] unii-wilanow: no late options and at least one option (known bug: N37 + N31 at 00:22 for an 08:30 query)
- [ ] politechnika-wilanow: no late options and at least one option (known bug: no option at all at 12:02 (one at 12:00), not even Veturilo for 7 km)

### Speed history from a walk + Veturilo ride (`history-veturilo-ride`): PASS

| Metric | Value |
|---|---|
| fixes sent | 503 |
| records | 2 |
| walking simulated (km/h) | 4.7 |
| cycling simulated (km/h) | 15.1 |
| walking from history (km/h) | 5.0 |
| cycling from history (km/h) | 14.5 |

- [x] walking: average 5.0 km/h within 10% of 4.7 km/h
- [x] cycling: average 14.5 km/h within 10% of 15.1 km/h
- [x] the records carry no coordinates

### Palace of Culture -> Galeria Mokotow by bus or tram (`trip-centrum-mokotow`): PASS

| Metric | Value |
|---|---|
| option | 521 + 18 |
| planned | 08:48-09:34 |
| leaves after the query (min) | 48.0 |
| planned duration (min) | 46 |
| travel time (min) | 46.6 |
| arrival vs plan (s, + = late) | 35.0 |
| end to destination (m) | 27.6 |
| waited at the stop (s) | 40.0 |
| detection requests while riding | 203 |
| ridden vehicle in top 4 (%) | 100.0 |
| ridden vehicle first (%) | 60.6 |

- [x] travel finished (ok)
- [x] the user ends within 150 m of the destination
- [x] the user arrives no later than the planned arrival + 3 min
- [x] a vehicle of every planned line was boarded
- [x] bus detection has the ridden vehicle in the top 4 for at least 90% of requests

### Veturilo Kabaty -> Ursynow, the pickup station runs empty (`veturilo-kabaty-ursynow`): PASS

| Metric | Value |
|---|---|
| pickup | Metro Kabaty |
| bikes before | 7 |
| bikes after | 0 |
| pickup after the change | Stryjeńskich - Wąwozowa |
| plan before | 17:00-17:42 (42 min) |
| plan after | 17:05-17:52 (47 min) |

- [x] the pickup station has bikes at the start
- [x] before the change the route still starts there
- [x] the change shows in /api/veturilo status after 5 min
- [x] after the change no option picks up a bike there
