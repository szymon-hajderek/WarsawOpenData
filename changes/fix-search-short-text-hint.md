# fix/search-short-text-hint

- With 1-2 typed characters and no matching stop, the search field said "Brak wyników w Warszawie", which looked like a broken search. It now says "Brak przystanków. Wpisz co najmniej 3 znaki, aby szukać adresów."
- Why it was empty: stop and Veturilo suggestions come from the backend (`GET /api/geocode`); without a running backend and its GTFS data the app falls back to Nominatim, which needs 3 characters.
