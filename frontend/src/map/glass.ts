import { GLASS, type StyleMode } from './palette';

/** Frosted glass of the round map buttons and markers (liquid glass look). */
export function glassStyle(mode: StyleMode, tint?: string) {
  const g = GLASS[mode];
  return {
    background: tint
      ? `linear-gradient(150deg, ${tint}, ${tint})`
      : `linear-gradient(150deg, ${g.glassTop}, ${g.glassBottom})`,
    backdropFilter: 'blur(14px) saturate(1.7)',
    WebkitBackdropFilter: 'blur(14px) saturate(1.7)',
    border: `1px solid ${g.glassBorder}`,
    boxShadow: `inset 0 1.5px 1px ${g.glassHighlight}, inset 0 -10px 18px ${g.glassBottom}, 0 10px 28px ${
      mode === 'dark' ? 'rgba(0, 0, 0, 0.5)' : 'rgba(160, 20, 40, 0.28)'
    }`,
  };
}

/** The same as a CSS declaration string, for the HTML of Leaflet markers. */
export const glassCss = (mode: StyleMode, tint?: string) =>
  Object.entries(glassStyle(mode, tint))
    .map(([k, v]) => `${k.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`).replace(/^webkit/, '-webkit')}:${v}`)
    .join(';');
