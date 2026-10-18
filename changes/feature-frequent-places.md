# feature/frequent-places

- Hidden "frequent places": every place of a route search (start, stops, destination; never the current
  location) gets a point on the device (`localStorage` `frequent-places`, nothing sent to the backend).
- Ranking: points halve every 30 days; the same place counts once per 10 minutes; max 50 places.
  A place is suggested from 1.5 points (two searches within 30 days).
- Every search field (`PlaceField`) shows up to 3 frequent places when empty (history icon,
  "Często wybierane") and the matching ones on top while typing, without duplicates.
- Preferences: "Wyczyść częste miejsca" button.
- Code: `frontend/src/places/` (`frequentPlaces.ts`, `FrequentPlacesProvider.tsx`, tests), `App.tsx`,
  `PlaceField.tsx`, `PreferencesPage.tsx`, `main.tsx`. No API change.
- Docs, test log and screenshots: `artifacts/frequent-places/` (`python artifacts/frequent-places/build.py`).
- Assumptions (decided without asking): the 10-minute dedup, the 50-place cap, threshold 1.5 instead of 2
  (exactly 2 failed after decay: the second search 11 minutes later gave 1.9998).
