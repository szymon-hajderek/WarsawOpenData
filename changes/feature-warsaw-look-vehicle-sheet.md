# Changes on `feature/warsaw-look-vehicle-sheet`

- Removed the old map look (OSM raster tiles) and its code / CSS. The flat vector map is now the only map.
- Added a second look in Warsaw colours (`warsaw`) next to the lavender one (default), each with a light and a night variant. The layers button switches between them (saved in the browser). All colours moved to `src/map/looks.ts`; the whole UI accent (theme, panels, chips) follows the look.
- Warsaw look: red is the main colour in light mode, yellow is an addition (gold secondary, warm yellow blocks / marker tints); at night yellow is the main accent.
- Added the "W jakim pojeździe jesteś?" window (`VehicleSheet`): open on the start screen, swipe down or tap to hide it into a bar, swipe up or tap to bring it back; 1 suggested vehicle + 3 others (mode + line + direction); "Jadę tą linią" confirms, "Nie jadę komunikacją" closes it.
- Renamed `mapVariant.tsx` -> `mapLook.tsx`, `styleV2.ts` -> `mapStyle.ts`; `createStyle` and `createAppTheme` now take the look.
- `AGENTS.md`: project knowledge updated.
- Assumptions: lavender stays the default; vehicle detection is a mock (`src/api/vehicle.ts`) returning made-up Warsaw lines; "Nie jadę komunikacją" hides the window until reload; the window is only shown on the start screen; the confirmed vehicle is kept in app state only (no effect on routing yet); the concept file `ui/concept-art/current-line-popup.paint` could not be opened, so the window was designed from the description; no fallback if the tile service is down; no new dependencies, so `README.md` setup is unchanged.
