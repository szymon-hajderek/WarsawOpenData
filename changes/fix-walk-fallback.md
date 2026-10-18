# fix/walk-fallback

- Transit search with no transit option at all (every mode excluded, nothing runs) returns the street-only trip of the
  profile however long, tagged `Bez komunikacji`, instead of an empty list. The 5 km / 50 min limit stays for the walk
  shown next to transit options.
