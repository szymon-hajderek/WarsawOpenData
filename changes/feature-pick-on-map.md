# Changes on `feature/pick-on-map`

- "Wybierz na mapie" in every place field (start, destination, intermediate stops).
- Picking state: a banner "Dotknij mapy, aby wybrać punkt" with "Anuluj" (and Escape) replaces the search card;
  a tap / click on the map (crosshair cursor on desktop) picks the point.
- The point becomes the nearest stop / Veturilo station within 60 m (`GET /api/stations`), else "Punkt na mapie";
  the search runs as usual.
- Long press / right click on the map: a small menu "Stąd" / "Dotąd".
- Tests: `src/pickOnMap.test.tsx`.
