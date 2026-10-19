# fix/map-trip-zoom

- Smaller map markers on the 2D map: transfers 38 -> 26 px, the user / destination 42-44 -> 32 px, intermediate stops
  30 -> 24 px, stop dots, metro entrances and elevator / steps icons smaller too.
- Active trip: the 2D map zooms to the leg being travelled (plus the user) each time the current leg changes (max
  zoom 17); it keeps following the user, panning only when the position nears the edge.
