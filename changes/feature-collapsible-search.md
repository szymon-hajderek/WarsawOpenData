# feature/collapsible-search

- The search card on a phone is folded by default to one field, "Dokąd jedziesz?", with a chevron. Opening it shows the card as it was (start, stops, travel modes, departure ...); a chevron in the open card folds it back. State `searchOpen` lives in `App`, so it survives a route search and back. The round map buttons move up or down with the card.
- Folded card with a destination and no start (no location yet): an "Ustaw start" button opens the card.
- Not folded: the desktop side panel, the ride demo (no toggle given), and a new search during an active trip (it keeps "Wróć do przejazdu" in view).
- The bus button on the map is a toggle now: first click detects and shows the vehicle window, second click hides it (a confirmed vehicle stays confirmed), third click shows it again without detecting; it is `aria-pressed` while the window is shown. The "Wykryj ponownie" button in the window still detects again.
- Tests: new `SearchCard.test.tsx` and `useVehicleToggle.test.ts`. The App-level tests (`activeTrip`, `pickOnMap`, `routeList`, `desktopLayout`) open the folded card first with `openSearchCard()` (`src/test/searchCard.ts`, does nothing on a wide screen). `testTimeout` is 20 s in `vite.config.ts`: the tests that render the whole App took about 5 s in a parallel run and failed at the old limit. Whole suite: 246 passed, twice in a row.
- Checked in the browser pane (phone size): folded by default, chevron opens / folds, map buttons move with the card, the bus button shows / hides / shows the window.
- Assumption: folded on every start (the choice is not saved).
