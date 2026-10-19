import { ICON_PATH, iconHtml } from '../modes';
import { unwrapRotation } from '../utils/heading';

/**
 * Inside of the "me" marker on both maps: the navigation arrow (shown when the heading is known)
 * and a plain dot (when it is not), so a still arrow never points the wrong way.
 */
export const userArrowHtml = (color: string, size = 24) =>
  `<div class="user-heading" style="display:none;transition:transform 0.3s ease-out">${iconHtml(ICON_PATH.navigation, size, color)}</div>` +
  `<div class="user-dot" style="width:${Math.round(size * 0.55)}px;height:${Math.round(size * 0.55)}px;border-radius:50%;background:${color}"></div>`;

/**
 * Turns the arrow inside `root` to `heading` (degrees from north), minus the map's own rotation
 * (`mapBearing`, the 3D map). The shortest turn: 350 -> 10 turns 20 degrees, not 340.
 */
export function applyHeading(root: HTMLElement | null | undefined, heading: number | null, mapBearing = 0) {
  const arrow = root?.querySelector<HTMLElement>('.user-heading');
  const dot = root?.querySelector<HTMLElement>('.user-dot');
  if (!arrow || !dot) return;
  arrow.style.display = heading == null ? 'none' : 'block';
  dot.style.display = heading == null ? 'block' : 'none';
  if (heading == null) return;
  const next = unwrapRotation(Number(arrow.dataset.rotation ?? 0), heading - mapBearing);
  arrow.dataset.rotation = String(next);
  arrow.style.transform = `rotate(${next}deg)`;
}
