# feature/frontend-route-segments

Frontend part of issue #83 (section 3b) and the `approximatePath` leg field (#85).

- `RouteLeg.segments?` (`kind`, `[lat, lon]` path, `lengthM`) and `RouteLeg.approximatePath?` in `src/types.ts`.
- `fetchStreetRoute` fills `segments` from `legs[0].segments` of `GET /api/osm/route` (`[lon, lat]` -> `[lat, lon]`,
  `length_m` -> `lengthM`); `isStreetAnswer` and `isRouteOptions` accept them (optional, a wrong shape is rejected).
- New pure helper `src/utils/legStyle.ts`: line style per segment / leg, connectors to the stop markers kept,
  ridden / pushed sums and leg notes.
- Map: ridden solid, pushed dashed (bike colour), steps / elevator / metro access in a short accent style;
  an `approximatePath` transit leg is dashed in its mode colour. A leg without segments is one line as before.
- Route details: "jazda X km, prowadzenie Y m" for a bike leg with segments, "przebieg orientacyjny" for an approximate path.
- Stroller checked live (real route with steps and an elevator); the 400 text stays only as a fallback for old servers.
- Tests with recorded bike and stroller router answers (`src/test/streetAnswers.ts`).
