# fix/backend-finish

- Veturilo can sit between two public-transport rides (`line + Veturilo + line`), not only before or after one ride.
- GTFS `shape_dist_traveled` is in kilometers. It is stored as meters, so a route leg follows the street between the boarded stops instead of a chopped kilometer.
- A live bus or tram matched by line and brigade shifts the shown departure and arrival when it is still at an earlier stop. The tag is `opóźnienie N min`. No key means no shift; the timetable route still returns.
