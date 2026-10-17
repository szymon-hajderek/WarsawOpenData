import type { LatLng, LonLat, Place, RouteOption } from '../types';
import { ROUTER_MODE, TRAVEL_LABELS, type StreetMode } from '../travel';
import { API_URL, apiUrl } from '../config';
import { formatTime } from '../utils/format';
import { BackendOfflineError } from './routes';
import { bestOrder, combineSegments } from './multiStop';
import type { StopOrder } from '../types';

/**
 * Street-only trips (walking, wheelchair, stroller, own bike), answered by the street router through
 * `GET /api/osm/route`. There is no mock and no straight line here, on purpose: for a wheelchair or a stroller the
 * user must know the path was really checked for steps.
 */

/** A failure with a text the user can read. */
export class StreetRouteError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const MESSAGES: Record<number, string> = {
  400: 'Ten tryb nie jest jeszcze dostępny na serwerze',
  404: 'Brak trasy',
  422: 'Punkt poza zasięgiem mapy',
  503: 'Serwer tras nie działa',
};
const messageFor = (status: number) => MESSAGES[status] ?? 'Serwer tras nie działa';

interface StreetAnswer {
  seconds: number;
  walk_m: number;
  bike_m: number;
  length_m: number;
  geometry: LatLng[];
  path?: LonLat[];
  elevators?: LonLat[];
  steps?: LonLat[];
}

const isPoint = (p: unknown): p is [number, number] =>
  Array.isArray(p) && p.length === 2 && p.every((n) => typeof n === 'number' && Number.isFinite(n));
const isPoints = (x: unknown) => x === undefined || (Array.isArray(x) && x.every(isPoint));

/** True when the answer has the numbers and the geometry the route is built from. */
export function isStreetAnswer(v: unknown): v is StreetAnswer {
  if (typeof v !== 'object' || v === null) return false;
  const a = v as Record<string, unknown>;
  return (
    ['seconds', 'walk_m', 'bike_m', 'length_m'].every((k) => typeof a[k] === 'number' && Number.isFinite(a[k] as number)) &&
    Array.isArray(a.geometry) &&
    a.geometry.length > 0 &&
    a.geometry.every(isPoint) &&
    isPoints(a.path) &&
    isPoints(a.elevators) &&
    isPoints(a.steps)
  );
}

const lonLat = (p: LatLng): LonLat => [p[1], p[0]];

/** The one-leg `RouteOption` of a router answer. */
export function streetOption(answer: StreetAnswer, from: Place, to: Place, mode: StreetMode, now = new Date()): RouteOption {
  const durationMin = Math.max(1, Math.round(answer.seconds / 60));
  const elevators = answer.elevators ?? [];
  const steps = answer.steps ?? [];
  const path = answer.geometry;
  const tags: string[] = [];
  if (mode === 'wheelchair' || mode === 'stroller') tags.push('bez schodów');
  if (elevators.length > 0) tags.push(`windy: ${elevators.length}`);
  return {
    id: `street-${mode}`,
    title: TRAVEL_LABELS[mode],
    legs: [
      {
        mode: mode === 'bike' ? 'bike' : 'walk',
        from: from.label,
        to: to.label,
        durationMin,
        distanceM: answer.length_m,
        start: lonLat(path[0]),
        end: lonLat(path[path.length - 1]),
        fromId: null,
        toId: null,
        path,
        elevators,
        steps,
      },
    ],
    departure: formatTime(now),
    arrival: formatTime(new Date(now.getTime() + durationMin * 60000)),
    durationMin,
    distanceM: answer.length_m,
    walkDistance: answer.walk_m,
    bikeDistance: answer.bike_m,
    transfers: 0,
    tags,
  };
}

/** One street path between two places. */
export async function fetchStreetRoute(from: Place, to: Place, mode: StreetMode, signal?: AbortSignal): Promise<RouteOption> {
  if (!API_URL) throw new StreetRouteError(503, 'Ta opcja wymaga serwera tras');
  const query = new URLSearchParams({
    from_lat: String(from.position[0]),
    from_lon: String(from.position[1]),
    to_lat: String(to.position[0]),
    to_lon: String(to.position[1]),
    mode: ROUTER_MODE[mode],
  });
  let res: Response;
  try {
    res = await fetch(apiUrl(`/api/osm/route?${query}`), { signal });
  } catch (err) {
    if (signal?.aborted) throw err;
    throw new BackendOfflineError();
  }
  if (!res.ok) throw new StreetRouteError(res.status, messageFor(res.status));
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    throw new StreetRouteError(502, messageFor(502));
  }
  if (!isStreetAnswer(data)) throw new StreetRouteError(502, messageFor(502));
  return streetOption(data, from, to, mode);
}

/** A street trip through the stops: one path per pair of points, chained like the transit trips. */
export async function fetchStreetTrip(
  { from, to, via = [], order = 'given' }: { from: Place; to: Place; via?: Place[]; order?: StopOrder },
  mode: StreetMode,
  signal?: AbortSignal,
): Promise<RouteOption[]> {
  const stops = order === 'optimal' ? bestOrder(from, via, to) : via;
  const points = [from, ...stops, to];
  const segments = await Promise.all(points.slice(1).map((p, i) => fetchStreetRoute(points[i], p, mode, signal)));
  return via.length === 0 ? segments : combineSegments(segments.map((s) => [s]), points);
}
