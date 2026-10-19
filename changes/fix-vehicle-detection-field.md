# fix/vehicle-detection-field

Field test (tram 24, 2026-10-18): no vehicle bar. Causes and fixes:
- The server must be able to read the City Hall live feed: a server outside Poland gets no answer, and every
  detection then returns 503 (deployment note, no code change).
- Automatic detection ran once, at the first fix: opening the app at the stop and boarding later never found the
  tram, and one position matched a passing bus 175 instead of the tram. Now it runs every 5 s once the track has 2
  points, until a vehicle is confirmed; "Nie jadę komunikacją" pauses it for 5 min. Also in the active trip.
- The feed lags the phone by ~10-20 s, so the own tram was 50-100 m "away" and over the 60 m limit. The backend now
  compares each phone point with the vehicle's position at that time (interpolated, or extrapolated along its last
  movement for at most 30 s): on live trams own vehicle first 60/60, median error 21 -> 11 m.
- The 60 m limit is removed (user decision): the best match is always offered; "Wykryliśmy" only when the second
  candidate is 2.5x worse.
- "Jadę tą linią" on the start screen sets the start to "Z pojazdu: <line> (następne przystanki)", so the next search plans from the vehicle (before, only "Zmień cel" in the active trip did).
- The confirmed vehicle ("Jedziesz: ...") is forgotten when the user has left it (2 checks in a row without it within 150 m), when a new route in the active trip is planned from the GPS position, and at "Zakończ".
