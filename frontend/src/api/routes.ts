import type { RouteSearchBody } from '../preferences/model';
import type { LatLng, Place, Profile, RouteLeg, RouteOption, StopOrder, TransportMode } from '../types';
import { buildPath, haversine, lonLat, slicePath, sumDistance } from '../utils/geo';
import { formatTime } from '../utils/format';
import { API_URL, apiUrl } from '../config';
import { isRouteOptions } from './validate';
import { bestOrder, combineSegments } from './multiStop';

/**
 * ROUTING SERVICE.
 *
 * `fetchRouteOptions` is the single seam between the UI and the backend. It calls
 * the FastAPI backend (`POST /api/routes`) when `API_URL` is set, and falls back to
 * the local mock (`mockRouteOptions`) only when the backend is switched off (`VITE_API_URL=""`);
 * when it is switched on but unreachable, the search fails with `BackendOfflineError`.
 */
export interface RouteQuery {
  from: Place;
  to: Place;
  profile: Profile;
  /** Intermediate stops (at most `MAX_STOPS`). */
  via?: Place[];
  /** Keep the stops as given, or reorder them for the shortest trip (start and destination stay fixed). */
  order?: StopOrder;
  /** Pace, transfers, excluded areas and body data. Omitted fields keep the backend defaults. */
  search?: RouteSearchBody;
  /** Warsaw local departure, ISO datetime or `HH:MM`. Empty = now (the demo sends the simulated time). */
  when?: string;
}

export interface RouteResult {
  options: RouteOption[];
  /** True when the options are made-up example data (the backend is off or sent a bad answer). */
  mock: boolean;
}

/** The backend could not be reached or sent an answer we cannot use (so the user is told, no made-up routes are shown). */
export class BackendOfflineError extends Error {
  constructor() {
    super('Backend unavailable');
  }
}

/** The backend answered, but refused the query (4xx): not a connection problem. */
class HttpError extends Error {
  constructor(readonly status: number) {
    super(`Routing failed: ${status}`);
  }
}

export async function fetchRouteOptions(query: RouteQuery, signal?: AbortSignal): Promise<RouteResult> {
  const { from, to, profile } = query;
  const via = query.via ?? [];
  const order = query.order ?? 'given';
  if (API_URL) {
    try {
      const res = await fetch(apiUrl('/api/routes'), {
        signal,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from, to, profile, ...(via.length ? { via, order } : {}), ...(query.when ? { when: query.when } : {}), ...query.search }),
      });
      if (!res.ok) throw new HttpError(res.status);
      const data: unknown = await res.json();
      if (!isRouteOptions(data)) throw new Error('Routing answer has an unexpected shape');
      return { options: data, mock: false };
    } catch (err) {
      if (signal?.aborted) throw err;
      if (err instanceof HttpError && err.status < 500) throw err;
      console.warn('Backend unavailable.', err);
      throw new BackendOfflineError();
    }
  }
  // Example routes only when the backend is switched off on purpose (`VITE_API_URL=""`).
  const options = via.length ? await mockMultiStop(query) : await mockRouteOptions(from, to, profile);
  return { options, mock: true };
}

/** Local fallback for trips with stops: one mock query per segment, chained like the backend does. */
async function mockMultiStop({ from, to, profile, via = [], order = 'given' }: RouteQuery): Promise<RouteOption[]> {
  const stops = order === 'optimal' ? bestOrder(from, via, to) : via;
  const points = [from, ...stops, to];
  const perSegment = await Promise.all(points.slice(1).map((p, i) => mockRouteOptions(points[i], p, profile, 0)));
  return combineSegments(perSegment, points);
}

interface TemplateLeg {
  mode: TransportMode;
  /** Share of the total distance (the shares of one template sum to 1). */
  share: number;
}

interface Template {
  id: string;
  title: string;
  legs: TemplateLeg[];
  bend: number;
  minDistanceM: number;
  maxDistanceM?: number;
}

const TEMPLATES: Template[] = [
  {
    id: 'veturilo',
    title: 'Veturilo',
    legs: [
      { mode: 'walk', share: 0.04 },
      { mode: 'veturilo', share: 0.92 },
      { mode: 'walk', share: 0.04 },
    ],
    bend: 0.06,
    minDistanceM: 1200,
    maxDistanceM: 15000,
  },
  {
    id: 'metro-bike',
    title: 'Metro + Veturilo',
    legs: [
      { mode: 'walk', share: 0.05 },
      { mode: 'metro', share: 0.6 },
      { mode: 'veturilo', share: 0.3 },
      { mode: 'walk', share: 0.05 },
    ],
    bend: 0.03,
    minDistanceM: 3000,
  },
  {
    id: 'bike-bus',
    title: 'Veturilo + autobus',
    legs: [
      { mode: 'veturilo', share: 0.25 },
      { mode: 'bus', share: 0.7 },
      { mode: 'walk', share: 0.05 },
    ],
    bend: 0.09,
    minDistanceM: 2500,
  },
  {
    id: 'tram',
    title: 'Tramwaj',
    legs: [
      { mode: 'walk', share: 0.06 },
      { mode: 'tram', share: 0.88 },
      { mode: 'walk', share: 0.06 },
    ],
    bend: -0.07,
    minDistanceM: 1500,
  },
  {
    id: 'metro',
    title: 'Metro',
    legs: [
      { mode: 'walk', share: 0.06 },
      { mode: 'metro', share: 0.88 },
      { mode: 'walk', share: 0.06 },
    ],
    bend: 0.02,
    minDistanceM: 2500,
  },
  {
    id: 'rail-bike',
    title: 'SKM + Veturilo',
    legs: [
      { mode: 'walk', share: 0.04 },
      { mode: 'rail', share: 0.72 },
      { mode: 'veturilo', share: 0.2 },
      { mode: 'walk', share: 0.04 },
    ],
    bend: -0.04,
    minDistanceM: 6000,
  },
  {
    id: 'walk',
    title: 'Pieszo',
    legs: [{ mode: 'walk', share: 1 }],
    bend: 0.03,
    minDistanceM: 0,
    maxDistanceM: 3500,
  },
];

// Speeds in km/h. Public transport speeds include stops.
const WALK_BIKE_SPEED: Record<Profile, { walk: number; bike: number }> = {
  standard: { walk: 4.8, bike: 15 },
  slow: { walk: 3.4, bike: 11 },
  accessible: { walk: 3.6, bike: 0 }, // no Veturilo for a wheelchair / stroller
  stroller: { walk: 3.6, bike: 0 },
};
const PT_SPEED: Partial<Record<TransportMode, number>> = { bus: 17, tram: 19, metro: 32, rail: 38 };
const PT_WAIT_MIN = 4;
const BIKE_UNLOCK_MIN = 1;
const DETOUR_FACTOR = 1.25; // straight line -> real street network


const LINES: Partial<Record<TransportMode, string[]>> = {
  bus: ['175', '186', '523'],
  tram: ['17', '18', '25', '33'],
  metro: ['M1', 'M2'],
  rail: ['S1', 'S2', 'S3'],
};
const STOP_NAME: Record<TransportMode, string> = {
  walk: '',
  bike: 'Stacja własnego roweru',
  veturilo: 'Stacja Veturilo',
  bus: 'Przystanek autobusowy',
  tram: 'Przystanek tramwajowy',
  metro: 'Stacja metra',
  rail: 'Stacja SKM',
};

// Name of the point where one leg ends and the next begins (the non-walking mode wins).
const nodeName = (a: TransportMode, b: TransportMode) => STOP_NAME[a !== 'walk' ? a : b];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function buildOption(
  template: Template,
  from: Place,
  to: Place,
  profile: Profile,
  distanceM: number,
  seed: number,
  departure: Date,
): RouteOption {
  const speeds = WALK_BIKE_SPEED[profile];
  const master = buildPath(from.position, to.position, template.bend, seed % 7);
  const totalM = distanceM * DETOUR_FACTOR;

  let cursor = 0;
  let ptBoarded = false;
  const legs: RouteLeg[] = template.legs.map((tl, i, all) => {
    const start = cursor;
    cursor += tl.share;
    const distM = totalM * tl.share;
    const lines = LINES[tl.mode];
    const line = lines ? lines[(seed + i) % lines.length] : undefined;

    let minutes: number;
    if (tl.mode === 'walk') minutes = (distM / 1000 / speeds.walk) * 60;
    else if (tl.mode === 'veturilo') minutes = (distM / 1000 / speeds.bike) * 60 + BIKE_UNLOCK_MIN;
    else {
      minutes = (distM / 1000 / (PT_SPEED[tl.mode] ?? 20)) * 60 + (ptBoarded ? 2 : PT_WAIT_MIN);
      ptBoarded = true;
    }

    const prev = i > 0 ? all[i - 1] : undefined;
    const next = i < all.length - 1 ? all[i + 1] : undefined;
    const path = slicePath(master, start, Math.min(1, cursor));
    return {
      mode: tl.mode,
      from: prev ? nodeName(prev.mode, tl.mode) : from.label,
      to: next ? nodeName(tl.mode, next.mode) : to.label,
      line,
      durationMin: Math.max(1, Math.round(minutes)),
      distanceM: distM,
      start: lonLat(path[0]),
      end: lonLat(path[path.length - 1]),
      fromId: null,
      toId: null,
      path,
    };
  });

  const durationMin = legs.reduce((s, l) => s + l.durationMin, 0);
  const nonWalk = legs.filter((l) => !['walk', 'bike', 'veturilo'].includes(l.mode)).length;
  const arrival = new Date(departure.getTime() + durationMin * 60000);

  return {
    id: template.id,
    title: template.title,
    legs,
    departure: formatTime(departure),
    arrival: formatTime(arrival),
    durationMin,
    distanceM: totalM,
    walkDistance: sumDistance(legs, ['walk']),
    bikeDistance: sumDistance(legs, ['bike', 'veturilo']),
    transfers: Math.max(0, nonWalk - 1),
    tags: [],
  };
}

/** Local fallback: generates plausible connections in the browser. */
async function mockRouteOptions(
  from: Place,
  to: Place,
  profile: Profile,
  latencyMs = 700,
): Promise<RouteOption[]> {
  await sleep(latencyMs); // simulates network latency

  const distanceM = haversine(from.position as LatLng, to.position as LatLng);
  const seed = Math.abs(Math.round((from.position[0] + to.position[1]) * 1000));
  const departure = new Date(Date.now() + 2 * 60000);

  const options = TEMPLATES.filter(
    (t) =>
      distanceM >= t.minDistanceM &&
      (t.maxDistanceM === undefined || distanceM <= t.maxDistanceM) &&
      !(profile === 'accessible' && t.legs.some((l) => l.mode === 'veturilo')),
  ).map((t) => buildOption(t, from, to, profile, distanceM, seed, departure));

  options.sort((a, b) => a.durationMin - b.durationMin);
  if (options.length === 0) return options;

  options[0].tags.push('Najszybsza');
  return options;
}
