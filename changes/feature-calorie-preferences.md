# feature/calorie-preferences

- New "Kalorie" section on the Preferences page: weight, height, age, sex (all optional, stay on the device in the `preferences` localStorage key).
- Calories shown in the route list, route details and the "Najaktywniejsze" sort are now computed in the app (`routeKcal` in `src/preferences/model.ts`):
  net kcal = MET x weight x hours minus resting energy, with MET interpolated from the user's walking / cycling / manual wheelchair speed.
- Research (what changes calories): body weight, speed, slope, carried load, mode, bike type / assist, sex, age, height, fitness, weather. Included now: weight, height, age, sex, speed, mode.
- Assumptions: default 70 kg / 170 cm / 35 y when empty; unknown sex = mean of both Mifflin-St Jeor formulas; electric wheelchair burns 0; transit legs count as resting;
  flat ground, no load, no slope (needs elevation data); body data is not overridable by time rules or filters; backend API unchanged.
