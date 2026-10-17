# Changes on `feature/preferences-and-filters`

- New bottom navigation bar with the tabs "Mapa" and "Preferencje"; floating panels (route list, vehicle window) moved above it.
- New Preferences tab: pace on foot, Veturilo riding level, wheelchair (none / manual / electric, step-free, low-floor only, prefer lifts), max transfers, excluded areas (Warsaw districts + own points with a radius). Each mode has an advancement level; "Zaawansowane" lets the user type an average speed in km/h instead.
- Time rules: any preference can change in given hours and days (e.g. "Noc"); the active rule is shown on the Preferences page and above the route list.
- Filters on the found routes (button "Filtry" + chips of active filters): sorting, max transfers, vehicles, max walking time, step-free, pace and wheelchair for this trip, excluded areas for this trip, and "Zaawansowane" with all preferences as overrides. They apply to the current search only.
- The route list shows a short summary of the preferences it follows. The old three profile chips (Standard / Wolniej / Wózek) were replaced by the filters.
- Preferences are stored in localStorage (`preferences`); "Przywróć domyślne" resets them.
- Assumptions: UI only - sorting, max transfers, vehicles and max walking time reorder / hide routes on the client, while speeds, wheelchair and areas are only stored and not used by the mock routing; overlapping time rules: the most recently started wins; custom speed ranges: walking 1-10, bike 3-45, wheelchair 1-15 km/h; filters reset when the start or destination changes.
- No new dependencies, so the `README.md` setup section is unchanged.
- `AGENTS.md`: project knowledge updated.
