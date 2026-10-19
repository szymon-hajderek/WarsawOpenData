import { BUS_1002_TRACK } from './busTrack';
import type { LatLng, RouteOption } from '../types';
import type { VehicleCandidate } from '../types';

/** Deterministic pseudo-random numbers (LCG), so the GPS noise is the same in every run. */
export function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

/** Moves a point by up to `radiusM` in a random direction (GPS error, like `algorithms/simulation`). */
export function withNoise(p: LatLng, radiusM: number, rnd: () => number): LatLng {
  const r = radiusM * Math.sqrt(rnd());
  const a = 2 * Math.PI * rnd();
  return [p[0] + (r * Math.sin(a)) / 111_320, p[1] + (r * Math.cos(a)) / (111_320 * Math.cos((p[0] * Math.PI) / 180))];
}

export const BUS_PATH: LatLng[] = BUS_1002_TRACK.map((p) => [p.lat, p.lon]);
const first = BUS_PATH[0];
const last = BUS_PATH[BUS_PATH.length - 1];
/** About 220 m north-east of the first bus position: where the user starts walking. */
export const WALK_START: LatLng = [first[0] + 0.0015, first[1] + 0.0015];
/** About 300 m south of the last bus position: the destination. */
export const DESTINATION: LatLng = [last[0] - 0.0027, last[1]];

/**
 * A constructed backend answer in the `RouteOption` format: walk to the stop, bus 119 along the recorded track of
 * bus-1002, walk to the destination. Stop names are made up.
 */
export const ROUTE_119: RouteOption = {
  id: 'pt-119-a',
  title: '119',
  legs: [
    { mode: 'walk', from: 'Start', to: 'Grochowska 01', durationMin: 3, distanceM: 220, path: [WALK_START, first], fromId: null, toId: 'ztm:200101' },
    {
      mode: 'bus',
      from: 'Grochowska 01',
      to: 'Rondo Wiatraczna 02',
      line: '119',
      durationMin: 3,
      distanceM: 1940,
      path: BUS_PATH,
      fromId: 'ztm:200101',
      toId: 'ztm:200202',
      tripId: 'ztm:119-trip-a',
    },
    { mode: 'walk', from: 'Rondo Wiatraczna 02', to: 'Cel', durationMin: 4, distanceM: 300, path: [last, DESTINATION], fromId: 'ztm:200202', toId: null },
  ],
  departure: '10:00',
  arrival: '10:10',
  durationMin: 10,
  distanceM: 2460,
  walkDistance: 520,
  bikeDistance: 0,
  transfers: 0,
  tags: ['Najszybsza'],
};

/** Constructed `POST /api/live/nearest-buses` answer (format of data/API.md): bus-1002 first, then 3 others. */
export const NEAREST_BUSES = {
  candidates: [
    { id: 'bus-1002', vehicle: '1002', line: '119', brigade: '2', mode: 'bus', direction: 'Dworzec Gdański', rmse_m: 14.2 },
    { id: 'bus-5914', vehicle: '5914', line: '175', brigade: '405', mode: 'bus', direction: 'Lotnisko Chopina', rmse_m: 310.5 },
    { id: 'tram-3120', vehicle: '3120', line: '9', brigade: '7', mode: 'tram', direction: 'P+R Al. Krakowska', rmse_m: 420.1 },
    { id: 'bus-7204', vehicle: '7204', line: '523', brigade: '3', mode: 'bus', direction: 'Stare Bemowo', rmse_m: 512.9 },
  ],
  lines: ['119', '175', '523', '9'],
  updated_at: 1792250711,
};

export const CANDIDATE_119: VehicleCandidate = { id: 'bus-1002', mode: 'bus', line: '119', direction: 'Dworzec Gdański' };

/** Constructed `POST /api/routes` answer with `onboard`: the first leg is the ride on bus-1002 (`fromId: null`). */
export function onboardRoute(to: LatLng): RouteOption {
  const off: LatLng = BUS_PATH[8];
  return {
    id: 'pt-onboard-119-b',
    title: '119',
    legs: [
      {
        mode: 'bus',
        from: 'Twoja pozycja',
        to: 'Wiatraczna 05',
        line: '119',
        durationMin: 2,
        distanceM: 900,
        path: BUS_PATH.slice(4, 9),
        fromId: null,
        toId: 'ztm:200305',
        tripId: 'ztm:119-trip-a',
      },
      { mode: 'walk', from: 'Wiatraczna 05', to: 'Nowy cel', durationMin: 6, distanceM: 450, path: [off, to], fromId: 'ztm:200305', toId: null },
    ],
    departure: '10:02',
    arrival: '10:10',
    durationMin: 8,
    distanceM: 1350,
    walkDistance: 450,
    bikeDistance: 0,
    transfers: 0,
    tags: ['Najszybsza'],
  };
}
