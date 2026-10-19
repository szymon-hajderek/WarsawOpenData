# fix/place-search-ztm-area

- Place search (Nominatim, backend and the browser fallback) covers the whole ZTM area (`config.BBOX`, the routing
  area) instead of a box around Warsaw: Piaseczno, Janki, Legionowo, Otwock... were routable but not findable.
- Backend `geocode.VIEWBOX` is built from `config.BBOX`; frontend `VIEWBOX` mirrors it (a test keeps them equal).
- Measured: local places ~25 ms, Nominatim ~1 s per query (the public server itself), cached repeat 4 ms.
