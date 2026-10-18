# feature/departure-time

- Search card: a "Wyjazd: Teraz" chip (`DepartureControl.tsx`) opens a small picker: Dziś / Jutro or any date,
  a time, "Teraz" (reset) and "Gotowe". A time that has already passed stays allowed but the chip is muted.
- State `departure` in `App.tsx` (not saved, resets to now on reload); a change runs a new search.
- `when` (`YYYY-MM-DDTHH:MM`, Warsaw local) is sent to `POST /api/routes` for transit, multi-stop and street-only
  trips; "Teraz" sends no `when`.
- The route list header says "Wyjazd 14:30" / "Wyjazd jutro 08:00" when the search was not for now.
- Helpers and labels in `src/utils/departure.ts`; tests in `src/utils/departure.test.ts`.
