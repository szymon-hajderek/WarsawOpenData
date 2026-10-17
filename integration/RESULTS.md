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

### Dworzec Wilenski -> Rondo Waszyngtona with a ZTM alert on the planned line (`alert-wilenski-waszyngtona`): PASS

| Metric | Value |
|---|---|
| alerted line | 25 |
| options after | 6 |
| options with the line | 2 |
| titles | 25 [Zmiana na trasie, Najszybsza], 3 + 7 [], 26 + 7 [], 25 + 7 [Zmiana na trasie], Veturilo [], Pieszo [Najaktywniejsza] |

- [x] no tag before the alert starts
- [x] an option still uses the line after the alert
- [x] every option with the line has the tag
- [x] no option without the line has the tag

### Dworzec Wilenski -> Rondo Waszyngtona with the tram 4 min late (`delay-wilenski-waszyngtona`): PASS

| Metric | Value |
|---|---|
| option | 25 |
| delayed vehicle | line 25, brigade 8 |
| set delay (s) | 240 |
| plan before | 08:33-08:41 |
| plan after | 08:37-08:45 |
| arrival shift (s) | 240.0 |
| arrival vs new plan (s, + = late) | 120.0 |
| tags after | opóźnienie 4 min, Najszybsza |

- [x] arrival moves by the delay (240 s +- 90 s)
- [x] the option has the tag 'opóźnienie N min' with N = 4 +- 1
- [x] the option had no delay tag before
- [x] travel finished (ok)
- [x] the user leaving at the new time arrives no later than the new plan + 3 min

### Route engine: options leave soon after the query (`engine-sanity`): PASS, 3 known bugs

| Metric | Value |
|---|---|
| pkin-galeria-mokotow | 3 options at 08:00; late: - |
| gorczewska-daszynskiego | 5 options at 08:30; late: - |
| zbawiciela-wilanowska | 2 options at 08:30; late: - |
| banacha-unii | 2 options at 12:00; late: - |
| dworzec-wschodni-zamek | 5 options at 08:30; late: - |
| unii-wilanow | 0 options at 08:30; late: - |
| politechnika-wilanow | 0 options at 12:02; late: - |
| tarchomin-mlociny | 1 options at 08:30; late: - |

- [x] pkin-galeria-mokotow: options exist and leave soon
- [x] gorczewska-daszynskiego: options exist and leave soon
- [x] zbawiciela-wilanowska: options exist and leave soon
- [x] banacha-unii: options exist and leave soon
- [x] dworzec-wschodni-zamek: options exist and leave soon
- [ ] unii-wilanow: options exist and leave soon (known bug: N37 + N31 at 00:22 for an 08:30 query)
- [ ] politechnika-wilanow: options exist and leave soon (known bug: no option at all at 12:02 (one at 12:00), not even Veturilo for 7 km)
- [ ] tarchomin-mlociny: options exist and leave soon (known bug: no public transport option at 08:30 for 4 km (ZTM buses link Tarchomin with Metro Młociny))

### Speed history from a walk + Veturilo ride (`history-veturilo-ride`): PASS

| Metric | Value |
|---|---|
| fixes sent | 480 |
| records | 2 |
| walking simulated (km/h) | 4.7 |
| cycling simulated (km/h) | 15.1 |
| walking from history (km/h) | 5.1 |
| cycling from history (km/h) | 14.3 |

- [x] walking: average 5.1 km/h within 10% of 4.7 km/h
- [x] cycling: average 14.3 km/h within 10% of 15.1 km/h
- [x] the records carry no coordinates

### Osiedle Gorczewska -> Rondo Daszynskiego by bus and tram (`trip-gorczewska-daszynskiego`): PASS

| Metric | Value |
|---|---|
| option | 122 + 11 |
| planned | 08:31-09:06 |
| leaves after the query (min) | 1.0 |
| planned duration (min) | 35 |
| travel time (min) | 35.8 |
| arrival vs plan (s, + = late) | 50.0 |
| end to destination (m) | 0.0 |
| waited at the stop (s) | 150.0 |
| detection requests while riding | 123 |
| ridden vehicle in top 4 (%) | 100.0 |
| ridden vehicle first (%) | 100.0 |

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
| plan before | 17:00-17:38 (38 min) |
| plan after | 17:05-17:49 (44 min) |

- [x] the pickup station has bikes at the start
- [x] before the change the route still starts there
- [x] the change shows in /api/veturilo status after 5 min
- [x] after the change no option picks up a bike there
