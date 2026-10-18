# fix/live-data-unavailable

- Vehicle detection: a 503 from `POST /api/live/nearest-buses` (no live feed / no `PORTAL_KEY` on the server) is
  "live data unavailable", not "not connected". The vehicle window says "Dane na żywo niedostępne" and offers manual
  line choice; the global "Nie połączono z serwerem" popup stays for real connection problems only.
