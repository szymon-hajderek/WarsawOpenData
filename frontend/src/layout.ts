/** Height of the bottom navigation bar; floating panels sit above it. */
export const BOTTOM_NAV_HEIGHT = 64;

/** CSS `bottom` of the floating panels (above the bottom bar). */
export const PANEL_BOTTOM = `calc(env(safe-area-inset-bottom) + ${BOTTOM_NAV_HEIGHT + 16}px)`;
