# feature/main-travel-modes

- Three main travel modes in the search card instead of five chips: Komunikacja | Pieszo | Rower.
- New accessibility toggle (Zwykle | Wózek inwalidzki | Wózek dziecięcy) under the modes, only for Komunikacja and Pieszo.
  Per search, not saved; a wheelchair in the preferences preselects "Wózek inwalidzki".
- Komunikacja sends `profile` standard / accessible / stroller (was always `standard`); a picked accessibility overrides
  the stepFree / wheelchair preferences for that search. Pieszo sends `travel` walk / accessible / stroller, Rower `travel` bike.
- Vehicle exclusions (`excludeModes`) are sent only with Komunikacja.
- Tests: `src/travel.test.tsx` (request of every mode + accessibility, exclusions, toggle hidden for Rower).
