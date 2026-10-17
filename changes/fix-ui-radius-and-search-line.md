# Changes on `fix/ui-radius-and-search-line`

- Fixed oversized rounded corners: in MUI `sx` a numeric `borderRadius` is multiplied by `theme.shape.borderRadius`, so values like `4` meant 64 px and the curve ran into icons and text (e.g. the cards on the Preferences page, the search fields, list rows). All corners now use one scale from `src/layout.ts` (`RADIUS`: sheet 28 px, card 20, tile / row / input 16, control 12, pill 999) with concentric corners. Theme `shape.borderRadius` is 12 and dialogs use the sheet radius.
- Removed the old (lavender) colour look and its switch: no layers button, no `mapLook` provider, no `map-variant` storage key. `src/map/looks.ts` became `src/map/palette.ts` with the single Warsaw palette (light + night).
- New line between the start circle and the pin in the search card: a rounded gradient line from the start colour (yellow) to the destination colour (red); the start icon and the pin take the same colours.
- Assumptions: the light / dark toggle stays; circles and pill-shaped buttons / chips stay fully round; the old localStorage value is ignored; visual changes only.
- `AGENTS.md`: Frontend section updated (one palette, radius scale and the MUI radius pitfall, the search line). No new dependencies, so the `README.md` setup is unchanged.
