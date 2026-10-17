/** Height of the bottom navigation bar; floating panels sit above it. */
export const BOTTOM_NAV_HEIGHT = 64;

/** CSS `bottom` of the floating panels (above the bottom bar). */
export const PANEL_BOTTOM = `calc(env(safe-area-inset-bottom) + ${BOTTOM_NAV_HEIGHT + 16}px)`;

/**
 * Corner radii (px). Use these instead of numbers: in MUI `sx` a numeric `borderRadius` is multiplied
 * by `theme.shape.borderRadius`, so `borderRadius: 4` would be 4 x 12 px. Nested corners: the inner
 * radius is the outer radius minus the padding, and content keeps about 0.7 x radius from a corner.
 */
export const RADIUS = {
  /** Bottom sheets, floating panels, dialogs, the search card. */
  sheet: '28px',
  /** Section cards. */
  card: '20px',
  /** Tiles, list rows, cards inside cards, input fields. */
  tile: '16px',
  /** Small controls and boxes inside cards. */
  control: '12px',
  /** Pills, handles, thin bars, chips, buttons. */
  pill: 999,
} as const;
