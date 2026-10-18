import type { LatLng, RouteLeg, RouteOption } from '../types';
import type { Station } from '../api/stations';
import { haversine } from './geo';

/**
 * The stop overlay of one route: where the stops are drawn and how the legs meet them.
 * Pure functions (the map only draws what they return).
 */

/** Closer than this (m) the end of a leg already is the stop; no connector is needed. */
const MEET_M = 2;
/** An entrance farther than this (m) from the walk that goes down is not "the" entrance of that walk. */
const ENTRANCE_M = 150;

export interface StopMarker {
  station: Station;
  /** Metro platforms are underground. */
  underground: boolean;
}

export interface Overlay {
  markers: StopMarker[];
  /** The path of every leg, with its ends moved onto the stop markers. */
  paths: LatLng[][];
  /** Metro: where the walk goes down (one entrance per metro platform, the one nearest to the walk). */
  entrances: LatLng[];
}

const isMetro = (s: Station) => s.kind === 'metro_platform';

function joinTo(path: LatLng[], at: LatLng | undefined, end: 'start' | 'end'): LatLng[] {
  if (!at || path.length === 0) return path;
  const edge = end === 'start' ? path[0] : path[path.length - 1];
  if (haversine(edge, at) <= MEET_M) return path;
  return end === 'start' ? [at, ...path] : [...path, at];
}

/** The ids a route names (`fromId` / `toId` of its legs), without repeats. */
export function stationIds(route: RouteOption | null): string[] {
  const ids = new Set<string>();
  for (const leg of route?.legs ?? []) {
    if (leg.fromId) ids.add(leg.fromId);
    if (leg.toId) ids.add(leg.toId);
  }
  return [...ids];
}

/** The point of a walking leg that touches the stop of the given end. */
function walkEdge(leg: RouteLeg | undefined, end: 'start' | 'end'): LatLng | undefined {
  if (!leg || leg.mode !== 'walk' || leg.path.length === 0) return undefined;
  return end === 'start' ? leg.path[0] : leg.path[leg.path.length - 1];
}

function nearestEntrance(station: Station, to: LatLng | undefined): LatLng | undefined {
  if (!to || station.entrances.length === 0) return undefined;
  let best: { p: LatLng; d: number } | undefined;
  for (const e of station.entrances) {
    const d = haversine(e, to);
    if (!best || d < best.d) best = { p: e, d };
  }
  return best && best.d <= ENTRANCE_M ? best.p : undefined;
}

/** Markers, joined paths and metro entrances for a route and the stations the server knows. */
export function buildOverlay(route: RouteOption, stations: ReadonlyMap<string, Station>): Overlay {
  const markers = new Map<string, StopMarker>();
  const entrances: LatLng[] = [];
  const entranceSeen = new Set<string>();

  const paths = route.legs.map((leg, i) => {
    const from = leg.fromId ? stations.get(leg.fromId) : undefined;
    const to = leg.toId ? stations.get(leg.toId) : undefined;
    for (const s of [from, to]) {
      if (s && !markers.has(s.id)) markers.set(s.id, { station: s, underground: isMetro(s) });
    }
    // where a walk goes down into a metro platform: the entrance nearest to the walk's end (or start when it comes up)
    for (const [s, edge] of [
      [from, walkEdge(route.legs[i - 1], 'end')],
      [to, walkEdge(route.legs[i + 1], 'start')],
    ] as const) {
      if (!s || !isMetro(s)) continue;
      const e = nearestEntrance(s, edge);
      if (e && !entranceSeen.has(`${e[0]},${e[1]}`)) {
        entranceSeen.add(`${e[0]},${e[1]}`);
        entrances.push(e);
      }
    }
    return joinTo(joinTo(leg.path, from?.position, 'start'), to?.position, 'end');
  });

  return { markers: [...markers.values()], paths, entrances };
}

export interface AccessPoint {
  key: string;
  kind: 'elevator' | 'steps';
  /** `[lat, lon]`, as the backend sends it. */
  position: LatLng;
}

/** Where the street legs of a route board an elevator or start a flight of steps (map markers). */
export function accessPoints(route: RouteOption): AccessPoint[] {
  return route.legs.flatMap((leg, i) => [
    ...(leg.elevators ?? []).map((position, k) => ({ key: `lift-${i}-${k}`, kind: 'elevator' as const, position })),
    ...(leg.steps ?? []).map((position, k) => ({ key: `steps-${i}-${k}`, kind: 'steps' as const, position })),
  ]);
}
