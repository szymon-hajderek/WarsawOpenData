# Veturilo station siting: trial report

> **T (car traffic) and E (e-scooters) are MOCK data** (`data/mock/`, fixed seed). S comes from OpenStreetMap,
> d_net from the OSM bike graph and the real Veturilo stations. Rebuild: `cd backend && uv run python siting_report.py`.

## Cost

J(p) = -α·T(p)·(1 + δ·E(p)) + β·P(d_net(p)) + γ·S(p),  P(d) = (1 - d/R)² for d < R, else 0. Lower is better.

Parameters: α = 1.0, β = 1.0, γ = 0.5, δ = 0.5, R = 1000 m, hex radius 175 m. Proposals are picked greedily: after each pick a station is placed there and d_net is updated (Dijkstra from the new station), so the next pick is not next door.

## Data

- 6476 hexes inside the Warsaw boundary; 5892 candidates (348 hexes already have one of 349 stations, 92 have no street).
- T: 1200 mock counters in 967 hexes; the rest by IDW (6 nearest, power 2); normalised to 0..1 at the 99th percentile.
- E: mock e-scooter crowding index 0..1 for 6476 hexagons of 175 m (the format the city receives from operators), averaged per our hex; our hexes without a value by IDW.
- S: length-weighted mean of the OSM street segments in the hex: 0 bike path (DDR / CPR), 0.3 quiet street or painted bike lane, 0.6 single-lane main road, 1.0 multi-lane / trunk road without a bike path.
- d_net: bike network (ridden + pushed), multi-source Dijkstra from all stations, up to 5000 m (91 hexes are farther).

| value | min | p25 | median | p75 | max | mean |
|---|---|---|---|---|---|---|
| T raw (cars / h) | 20 | 198 | 326 | 512 | 2289 | 389 |
| T | 0.00 | 0.15 | 0.26 | 0.42 | 1.00 | 0.31 |
| E | 0.00 | 0.00 | 0.22 | 0.42 | 1.00 | 0.26 |
| S | 0.00 | 0.30 | 0.30 | 0.31 | 0.91 | 0.31 |
| d_net (m) | 0 | 561 | 1128 | 2134 | 5382 | 1447 |

## Top proposals

| # | hex | lat, lon | J | T | E | d_net (m) | P | S |
|---|---|---|---|---|---|---|---|---|
| 1 | -6331:22123 | 52.22619, 21.05326 | -1.165 | 1.00 | 0.74 | 1241 | 0.000 | 0.41 |
| 2 | -6352:22121 | 52.22147, 20.95535 | -1.153 | 1.00 | 0.65 | 848 | 0.023 | 0.30 |
| 3 | -6352:22141 | 52.26868, 20.99986 | -1.130 | 1.00 | 0.57 | 924 | 0.006 | 0.30 |
| 4 | -6322:22115 | 52.20730, 21.07552 | -1.092 | 1.00 | 0.51 | 1040 | 0.000 | 0.33 |
| 5 | -6350:22120 | 52.21911, 20.96203 | -1.085 | 1.00 | 0.66 | 720 | 0.078 | 0.33 |
| 6 | -6361:22136 | 52.25688, 20.94868 | -1.074 | 1.00 | 0.51 | 1129 | 0.000 | 0.37 |
| 7 | -6381:22163 | 52.32062, 20.91975 | -1.058 | 1.00 | 0.32 | 2479 | 0.000 | 0.21 |
| 8 | -6351:22121 | 52.22147, 20.95980 | -1.057 | 1.00 | 0.64 | 753 | 0.061 | 0.40 |
| 9 | -6321:22112 | 52.20022, 21.07329 | -1.035 | 1.00 | 0.22 | 996 | 0.000 | 0.15 |
| 10 | -6319:22119 | 52.21675, 21.09777 | -1.029 | 1.00 | 0.54 | 1193 | 0.000 | 0.48 |

d_net is the distance at the moment of the pick (after the earlier picks).
Interactive map: `artifacts/veturilo-siting/veturilo-siting.html`. API: `GET /api/veturilo/siting` (`data/API.md`).
