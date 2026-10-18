import type { LatLng, RouteLeg, SegmentKind } from '../types';
import { formatDistance } from './format';

/**
 * How the map draws a leg: pure helpers (the map only turns the styles into Leaflet options).
 * - `solid`: a ridden bike part, a ride with a real path;
 * - `dashed`: a pushed bike part, or a transit leg with an approximate path (straight line through the stops);
 * - `dotted`: walking;
 * - `access`: steps, an elevator, the walk down to a metro platform.
 */
export type LineStyle = 'solid' | 'dashed' | 'dotted' | 'access';

export const SEGMENT_KINDS: readonly SegmentKind[] = ['ride', 'push', 'walk', 'steps', 'elevator', 'metro_access'];

export interface LegLine {
  path: LatLng[];
  style: LineStyle;
}

export function segmentStyle(kind: SegmentKind): LineStyle {
  switch (kind) {
    case 'ride':
      return 'solid';
    case 'push':
      return 'dashed';
    case 'walk':
      return 'dotted';
    default:
      return 'access';
  }
}

/** The style of a leg drawn as one line (no segments). */
export function legStyle(leg: RouteLeg): LineStyle {
  if (leg.mode === 'walk') return 'dotted';
  return leg.approximatePath ? 'dashed' : 'solid';
}

const same = (a: LatLng, b: LatLng) => a[0] === b[0] && a[1] === b[1];

/**
 * The lines of one leg. `joined` is the leg's path with its ends moved onto the stop markers (`buildOverlay`):
 * a leg without segments is drawn as that one line; with segments, the connectors to the stops are added to the
 * first and the last segment, so consecutive legs still meet at the markers.
 */
export function legLines(leg: RouteLeg, joined: LatLng[] = leg.path): LegLine[] {
  const segments = (leg.segments ?? []).filter((s) => s.path.length > 0);
  if (segments.length === 0) return [{ path: joined, style: legStyle(leg) }];
  const lines = segments.map((s) => ({ path: s.path, style: segmentStyle(s.kind) }));
  if (joined.length > 0) {
    const first = lines[0];
    const last = lines[lines.length - 1];
    if (!same(joined[0], first.path[0])) first.path = [joined[0], ...first.path];
    const end = joined[joined.length - 1];
    if (!same(end, last.path[last.path.length - 1])) last.path = [...last.path, end];
  }
  return lines;
}

/** Ridden and pushed metres of a bike leg with segments (`null` otherwise). Everything not ridden counts as pushed. */
export function bikeSplit(leg: RouteLeg): { rideM: number; pushM: number } | null {
  if (leg.mode !== 'bike' || !leg.segments?.length) return null;
  let rideM = 0;
  let pushM = 0;
  for (const s of leg.segments) {
    if (s.kind === 'ride') rideM += s.lengthM;
    else pushM += s.lengthM;
  }
  return { rideM, pushM };
}

/** Extra facts of a leg: ridden vs pushed bike, an approximate transit path. */
export function legNotes(leg: RouteLeg): string[] {
  const notes: string[] = [];
  const split = bikeSplit(leg);
  if (split) notes.push(`jazda ${formatDistance(split.rideM)}, prowadzenie ${formatDistance(split.pushM)}`);
  if (leg.approximatePath) notes.push('przebieg orientacyjny');
  return notes;
}
