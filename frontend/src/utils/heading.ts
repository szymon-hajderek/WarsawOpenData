import type { LatLng } from '../types';
import { haversine } from './geo';

/**
 * Heading of the user's arrow, in degrees clockwise from north (0..360).
 * Pure helpers: the compass reading of a `deviceorientation` event, the direction of movement
 * from the last 3 well-spaced GPS fixes, smoothing and the shortest turn for the CSS rotation.
 */

const toRad = (deg: number) => (deg * Math.PI) / 180;
const toDeg = (rad: number) => (rad * 180) / Math.PI;

export const norm = (deg: number) => ((deg % 360) + 360) % 360;

/** Signed shortest turn from `a` to `b` (-180..180). */
export const angleDiff = (a: number, b: number) => norm(b - a + 180) - 180;

/** Initial bearing from `a` to `b` (degrees clockwise from north). */
export function bearing(a: LatLng, b: LatLng): number {
  const [la1, lo1, la2, lo2] = [toRad(a[0]), toRad(a[1]), toRad(b[0]), toRad(b[1])];
  const y = Math.sin(lo2 - lo1) * Math.cos(la2);
  const x = Math.cos(la1) * Math.sin(la2) - Math.sin(la1) * Math.cos(la2) * Math.cos(lo2 - lo1);
  return norm(toDeg(Math.atan2(y, x)));
}

/** Fields of a `deviceorientation(absolute)` event we read (iOS adds the webkit ones). */
export interface OrientationLike {
  alpha: number | null;
  absolute?: boolean;
  webkitCompassHeading?: number;
  webkitCompassAccuracy?: number;
}

/**
 * Where the top of the screen points, from one orientation event, or null when the event is not
 * a compass reading (relative alpha, no data, uncalibrated iOS compass).
 * `screenAngle` = screen rotation (0 portrait, 90 / 270 landscape).
 */
export function compassHeading(e: OrientationLike, screenAngle: number, absoluteEvent: boolean): number | null {
  if (typeof e.webkitCompassHeading === 'number' && e.webkitCompassHeading >= 0) {
    if (typeof e.webkitCompassAccuracy === 'number' && e.webkitCompassAccuracy < 0) return null;
    return norm(e.webkitCompassHeading + screenAngle);
  }
  if (e.alpha == null || !(absoluteEvent || e.absolute)) return null;
  return norm(360 - e.alpha + screenAngle);
}

/** A kept GPS fix for the movement direction (`time` in ms). */
export interface Fix {
  pos: LatLng;
  accuracy: number;
  time: number;
}

/** Fixes worse than this (network / Wi-Fi location, the first coarse fix) never give a direction. */
export const MAX_ACCURACY_M = 30;
/** A new fix counts only this far (m) from the last kept one: max(accuracy of both, MIN). */
export const STEP_MIN_M = 10;
export const MOVE_POINTS = 3;
/** Fixes older than this are forgotten: an old fix plus new drift is not a direction. */
export const FIX_TTL_MS = 60_000;
/** No new kept fix for this long = the user stopped: the direction is unknown again. */
export const MOVE_STALE_MS = 30_000;
/** A zigzag (the path turns by more than this between the 3 fixes) is drift, not walking. */
export const MAX_TURN_DEG = 120;

/**
 * Adds a fix to the last 3 well-spaced, recent fixes. A coarse fix is ignored and a fix closer to the last
 * kept one than the GPS error is jitter, not movement, so standing still never turns the arrow.
 */
export function addFix(kept: Fix[], fix: Fix): Fix[] {
  if (!(fix.accuracy > 0) || fix.accuracy > MAX_ACCURACY_M) return kept;
  const fresh = kept.filter((f) => fix.time - f.time <= FIX_TTL_MS);
  const last = fresh[fresh.length - 1];
  const step = Math.max(STEP_MIN_M, fix.accuracy, last?.accuracy ?? 0);
  if (last && haversine(last.pos, fix.pos) < step) return fresh.length === kept.length ? kept : fresh;
  return [...fresh, fix].slice(-MOVE_POINTS);
}

/**
 * Direction of movement from the oldest to the newest kept fix, or null: fewer than 2 fixes, the newest
 * older than `MOVE_STALE_MS` (the user stopped) or a zigzag of 3 fixes.
 */
export function movementHeading(kept: Fix[], now: number): number | null {
  if (kept.length < 2 || now - kept[kept.length - 1].time > MOVE_STALE_MS) return null;
  if (kept.length === 3) {
    const turn = angleDiff(bearing(kept[0].pos, kept[1].pos), bearing(kept[1].pos, kept[2].pos));
    if (Math.abs(turn) > MAX_TURN_DEG) return null;
  }
  return bearing(kept[0].pos, kept[kept.length - 1].pos);
}

/** Exponential smoothing of an angle (through the unit vector, so 359 -> 1 is not a full turn). */
export function smoothAngle(prev: number | null, next: number, factor: number): number {
  if (prev == null) return norm(next);
  const x = (1 - factor) * Math.cos(toRad(prev)) + factor * Math.cos(toRad(next));
  const y = (1 - factor) * Math.sin(toRad(prev)) + factor * Math.sin(toRad(next));
  return norm(toDeg(Math.atan2(y, x)));
}

/** CSS rotation that reaches `heading` from the last applied rotation by the shortest turn (no 359 -> 0 spin). */
export const unwrapRotation = (applied: number, heading: number) => applied + angleDiff(norm(applied), heading);
