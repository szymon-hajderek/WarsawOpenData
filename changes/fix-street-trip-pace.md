# fix/street-trip-pace

- Street-only trips ("Pieszo", "Na wózku", "Z wózkiem dziecięcym", "Rower") now send the user's pace (`walkKmh`,
  `bikeKmh` for the bike) like the transit search. Before, "Rower" used the backend default (15 km/h) while
  "Komunikacja + Z własnym rowerem" used the preference (13 km/h), so bike-only looked faster than the bike legs of
  a mixed trip. No API change (`travel` already accepted the speeds).
