import type { LatLng, RouteLeg, RouteOption } from '../types';

/** Farther than this from the route = "Zboczyłeś z trasy". */
export const OFF_ROUTE_M = 150;
/** How far back a new position may project (GPS noise), metres; more is ignored: progress only goes forward. */
const BACK_TOLERANCE_M = 40;

const TRANSIT = new Set<RouteLeg['mode']>(['bus', 'tram', 'metro', 'rail']);
export const isTransit = (leg: RouteLeg) => TRANSIT.has(leg.mode);

export interface TripProgress {
  /** Index of the leg the user is on now. */
  legIndex: number;
  /** Distance along the whole route (all leg paths joined), metres. Never goes back. */
  alongM: number;
  /** Distance from the position to the route, metres. */
  offsetM: number;
  offRoute: boolean;
  /** "Wysiadasz na: X", "Przesiadka: 175 z X", "Idź do: X", ... */
  nextStep: string;
}

interface Segment {
  a: LatLng;
  b: LatLng;
  leg: number;
  /** Route distance at `a`. */
  startM: number;
  lengthM: number;
}

const M_PER_DEG = 111_320;

/** Local flat projection around `ref` (metres east, north): good enough for a few km. */
function xy(p: LatLng, ref: LatLng): [number, number] {
  return [(p[1] - ref[1]) * M_PER_DEG * Math.cos((ref[0] * Math.PI) / 180), (p[0] - ref[0]) * M_PER_DEG];
}

function segments(route: Pick<RouteOption, 'legs'>): Segment[] {
  const out: Segment[] = [];
  let total = 0;
  route.legs.forEach((leg, i) => {
    for (let k = 1; k < leg.path.length; k++) {
      const a = leg.path[k - 1];
      const [bx, by] = xy(leg.path[k], a);
      const lengthM = Math.hypot(bx, by);
      out.push({ a, b: leg.path[k], leg: i, startM: total, lengthM });
      total += lengthM;
    }
  });
  return out;
}

/** Closest point of a segment: distance to it and how far along the segment it lies. */
function project(p: LatLng, s: Segment): { dist: number; t: number } {
  const [px, py] = xy(p, s.a);
  const [bx, by] = xy(s.b, s.a);
  const len2 = bx * bx + by * by;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, (px * bx + py * by) / len2));
  return { dist: Math.hypot(px - t * bx, py - t * by), t };
}

/** The text of the next thing to do while on leg `i`. */
export function nextStepText(legs: RouteLeg[], i: number): string {
  const leg = legs[i];
  if (!leg) return '';
  if (isTransit(leg)) return `Wysiadasz na: ${leg.to}`;
  const next = legs[i + 1];
  const rodeBefore = legs.slice(0, i).some(isTransit);
  if (next && isTransit(next) && rodeBefore) return `Przesiadka: ${next.line ?? ''} z ${next.from}`.replace('  ', ' ');
  if (leg.mode === 'bike' || leg.mode === 'veturilo') return `Jedź do: ${leg.to}`;
  return `Idź do: ${leg.to}`;
}

/**
 * Where the user is on the route: the position is projected on the leg paths, forward only (`prevAlongM` =
 * the previous result, 0 at the start). Pure; the caller keeps `alongM` between positions.
 */
export function routeProgress(route: Pick<RouteOption, 'legs'>, position: LatLng, prevAlongM = 0): TripProgress {
  const segs = segments(route);
  if (segs.length === 0) {
    return { legIndex: 0, alongM: prevAlongM, offsetM: 0, offRoute: false, nextStep: nextStepText(route.legs, 0) };
  }
  let best: { dist: number; along: number; leg: number } | null = null;
  for (const s of segs) {
    if (s.startM + s.lengthM < prevAlongM - BACK_TOLERANCE_M) continue; // behind us
    const { dist, t } = project(position, s);
    if (!best || dist < best.dist - 1e-6) best = { dist, along: s.startM + t * s.lengthM, leg: s.leg };
  }
  if (!best) {
    // past the end of the route
    const last = segs[segs.length - 1];
    best = { dist: project(position, last).dist, along: last.startM + last.lengthM, leg: last.leg };
  }
  const offRoute = best.dist > OFF_ROUTE_M;
  // Off the route the progress stays where it was; on it, it never goes back.
  const alongM = offRoute ? prevAlongM : Math.max(prevAlongM, best.along);
  const legIndex = legAt(segs, alongM, route.legs.length);
  return { legIndex, alongM, offsetM: best.dist, offRoute, nextStep: nextStepText(route.legs, legIndex) };
}

function legAt(segs: Segment[], alongM: number, legCount: number): number {
  for (const s of segs) if (alongM < s.startM + s.lengthM) return s.leg;
  return Math.max(0, legCount - 1);
}
