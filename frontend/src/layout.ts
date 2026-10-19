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

/**
 * Width of the side panel on a wide screen (px): from `sm` (600 px) the search card and the sheets sit in one
 * scrollable column on the left and the map fills the rest (no overlap); narrower on tablets.
 */
export const PANEL_WIDTH = { sm: 360, md: 420 } as const;

/**
 * Margins kept free around a route on a wide screen (px). The map starts right of the side panel, so the panel
 * never covers it; the right margin leaves room for the map buttons.
 */
export const MAP_PADDING = {
  desktop: { top: 40, left: 40, bottom: 40, right: 80 },
} as const;
