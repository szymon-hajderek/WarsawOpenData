import type { LatLng, Place, Profile, RouteLeg, RouteOption, TransportMode } from '../types';
import { buildPath, haversine, slicePath } from '../utils/geo';
import { formatTime } from '../utils/format';

/**
 * ROUTING SERVICE - MOCK.
 *
 * `fetchRouteOptions` is the single seam between the UI and the backend. For now
 * it generates plausible connections locally; once FastAPI + OpenTripPlanner are
 * ready, replace the body with a call to the API returning the same `RouteOption[]`.
 */

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
    id: 'bike',
    title: 'Veturilo',
    legs: [
      { mode: 'walk', share: 0.04 },
      { mode: 'bike', share: 0.92 },
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
      { mode: 'bike', share: 0.3 },
      { mode: 'walk', share: 0.05 },
    ],
    bend: 0.03,
    minDistanceM: 3000,
  },
  {
    id: 'bike-bus',
    title: 'Veturilo + autobus',
    legs: [
      { mode: 'bike', share: 0.25 },
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
      { mode: 'bike', share: 0.2 },
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
};
const PT_SPEED: Partial<Record<TransportMode, number>> = { bus: 17, tram: 19, metro: 32, rail: 38 };
const PT_WAIT_MIN = 4;
const BIKE_UNLOCK_MIN = 1;
const DETOUR_FACTOR = 1.25; // straight line -> real street network

const KCAL_PER_KM = { walk: 55, bike: 32 };
const TICKET_PLN = 4.4; // estimate: 20-minute ticket
const VETURILO_FREE_MIN = 20;

const LINES: Partial<Record<TransportMode, string[]>> = {
  bus: ['175', '186', '523'],
  tram: ['17', '18', '25', '33'],
  metro: ['M1', 'M2'],
  rail: ['S1', 'S2', 'S3'],
};
const STOP_NAME: Record<TransportMode, string> = {
  walk: '',
  bike: 'Stacja Veturilo',
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
    else if (tl.mode === 'bike') minutes = (distM / 1000 / speeds.bike) * 60 + BIKE_UNLOCK_MIN;
    else {
      minutes = (distM / 1000 / (PT_SPEED[tl.mode] ?? 20)) * 60 + (ptBoarded ? 2 : PT_WAIT_MIN);
      ptBoarded = true;
    }

    const prev = i > 0 ? all[i - 1] : undefined;
    const next = i < all.length - 1 ? all[i + 1] : undefined;
    return {
      mode: tl.mode,
      from: prev ? nodeName(prev.mode, tl.mode) : from.label,
      to: next ? nodeName(tl.mode, next.mode) : to.label,
      line,
      durationMin: Math.max(1, Math.round(minutes)),
      distanceM: distM,
      path: slicePath(master, start, Math.min(1, cursor)),
    };
  });

  const durationMin = legs.reduce((s, l) => s + l.durationMin, 0);
  const bikeMin = legs.filter((l) => l.mode === 'bike').reduce((s, l) => s + l.durationMin, 0);
  const usesPt = legs.some((l) => PT_SPEED[l.mode]);
  const calories = Math.round(
    legs.reduce((s, l) => {
      if (l.mode === 'walk') return s + (l.distanceM / 1000) * KCAL_PER_KM.walk;
      if (l.mode === 'bike') return s + (l.distanceM / 1000) * KCAL_PER_KM.bike;
      return s;
    }, 0),
  );
  const nonWalk = legs.filter((l) => l.mode !== 'walk').length;
  const arrival = new Date(departure.getTime() + durationMin * 60000);

  return {
    id: template.id,
    title: template.title,
    legs,
    departure: formatTime(departure),
    arrival: formatTime(arrival),
    durationMin,
    distanceM: totalM,
    calories,
    transfers: Math.max(0, nonWalk - 1),
    costPln: (usesPt ? TICKET_PLN : 0) + (bikeMin > VETURILO_FREE_MIN ? 1 : 0),
    tags: [],
  };
}

export async function fetchRouteOptions(
  from: Place,
  to: Place,
  profile: Profile,
): Promise<RouteOption[]> {
  await sleep(700); // simulates network latency

  const distanceM = haversine(from.position as LatLng, to.position as LatLng);
  const seed = Math.abs(Math.round((from.position[0] + to.position[1]) * 1000));
  const departure = new Date(Date.now() + 2 * 60000);

  const options = TEMPLATES.filter(
    (t) =>
      distanceM >= t.minDistanceM &&
      (t.maxDistanceM === undefined || distanceM <= t.maxDistanceM) &&
      !(profile === 'accessible' && t.legs.some((l) => l.mode === 'bike')),
  ).map((t) => buildOption(t, from, to, profile, distanceM, seed, departure));

  options.sort((a, b) => a.durationMin - b.durationMin);
  if (options.length === 0) return options;

  options[0].tags.push('Najszybsza');
  const minCost = Math.min(...options.map((o) => o.costPln));
  const cheapest = options.filter((o) => o.costPln === minCost);
  if (cheapest.length === 1 && options.length > 1) cheapest[0].tags.push('Najtańsza');
  const mostActive = options.reduce((a, b) => (b.calories > a.calories ? b : a));
  if (mostActive.calories > 0 && options.length > 1 && mostActive.tags.length < 2) {
    mostActive.tags.push('Najaktywniejsza');
  }
  return options;
}
