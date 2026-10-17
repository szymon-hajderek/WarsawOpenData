import type { LatLng, VehicleCandidate } from '../types';

/**
 * VEHICLE DETECTION - MOCK.
 *
 * `detectVehicle` answers "which public transport vehicle is the user inside of?". The real
 * service will use the user's location and the history of vehicle positions. Replace the body
 * with a call to the backend returning the same `VehicleCandidate[]`: the most likely vehicle
 * first, then up to 3 other possible ones.
 */
const POOL: VehicleCandidate[] = [
  { id: 'tram-17', mode: 'tram', line: '17', direction: 'Annopol' },
  { id: 'bus-175', mode: 'bus', line: '175', direction: 'Lotnisko Chopina' },
  { id: 'metro-m1', mode: 'metro', line: 'M1', direction: 'Kabaty' },
  { id: 'rail-s1', mode: 'rail', line: 'S1', direction: 'Otwock' },
  { id: 'bus-523', mode: 'bus', line: '523', direction: 'Dw. Wschodni' },
  { id: 'tram-33', mode: 'tram', line: '33', direction: 'Okęcie' },
  { id: 'metro-m2', mode: 'metro', line: 'M2', direction: 'Bemowo' },
  { id: 'bus-186', mode: 'bus', line: '186', direction: 'Wilanów' },
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function detectVehicle(position: LatLng | null): Promise<VehicleCandidate[]> {
  await sleep(500); // simulates network latency

  // Without a location: the most popular lines. With one: a different, stable set per place.
  const start = position ? Math.abs(Math.round((position[0] + position[1]) * 1000)) % POOL.length : 0;
  return [0, 3, 5, 7].map((step) => POOL[(start + step) % POOL.length]);
}
