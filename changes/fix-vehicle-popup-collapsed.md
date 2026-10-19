# fix/vehicle-popup-collapsed

- The vehicle window never opens by itself as the big sheet: a small collapsed bar instead.
  Confident = "Wykryliśmy, że jedziesz linią 131 → Sadyba" + "Zmień"; plausible but not sure = "Czy jedziesz tym
  pojazdem? Autobus 131". Both expand on tap.
- Plausibility limit 120 m -> 60 m (a real match is ~40-50 m; the error is mostly the feed lag). No speed rule: a bus
  standing at the user position (RMSE ~0) is the best match.
