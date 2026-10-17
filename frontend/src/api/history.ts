import { API_URL } from '../config';
import type { TransportMode } from '../types';
import {
  EMPTY_SUMMARY,
  MIN_TRIPS,
  type SpeedMode,
  type SpeedSummary,
  type TrackPoint,
  type TripRecord,
} from '../history/types';

/**
 * SPEED HISTORY.
 *
 * The backend only computes (`POST /api/history/records`, `POST /api/history/summary`); it stores nothing.
 * The device keeps the records (no coordinates). `fetchTripRecords` needs the backend; `fetchSummary` falls
 * back to a small local calculation when the backend is unreachable.
 */

export interface PlannedLeg {
  mode: TransportMode;
  distanceM: number;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  if (!API_URL) throw new Error('backend disabled');
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`History request failed: ${res.status}`);
  return (await res.json()) as T;
}

/** Turns a GPS track of a ridden route into per-mode records. Empty when the track is too short or does not fit the route. */
export async function fetchTripRecords(
  track: TrackPoint[],
  legs: PlannedLeg[],
  walkAs: 'walking' | 'wheelchair',
): Promise<TripRecord[]> {
  const data = await post<{ records: TripRecord[] }>('/api/history/records', {
    track,
    legs,
    walkAs,
    at: new Date().toISOString(),
  });
  return data.records;
}

/** Same rules as `algorithms/speed_history.summarize` (used when the backend is unreachable). */
export function localSummary(records: TripRecord[], minTrips = MIN_TRIPS, window = 20): SpeedSummary {
  const result = structuredClone(EMPTY_SUMMARY);
  (Object.keys(result) as SpeedMode[]).forEach((mode) => {
    const mine = records.filter((r) => r.mode === mode).sort((a, b) => a.at.localeCompare(b.at)).slice(-window);
    if (mine.length === 0) return;
    const speeds = mine.map((r) => r.kmh).sort((a, b) => a - b);
    const mid = Math.floor(speeds.length / 2);
    const median = speeds.length % 2 ? speeds[mid] : (speeds[mid - 1] + speeds[mid]) / 2;
    const kept = mine.length >= 5 ? mine.filter((r) => Math.abs(r.kmh - median) <= 0.5 * median) : mine;
    const distance = kept.reduce((s, r) => s + r.distanceM, 0);
    const seconds = kept.reduce((s, r) => s + r.durationS, 0);
    result[mode] = {
      trips: mine.length,
      distanceKm: Math.round(distance / 100) / 10,
      avgKmh: seconds > 0 ? Math.round(((distance / seconds) * 3.6) * 10) / 10 : null,
      medianKmh: Math.round(median * 10) / 10,
      enough: mine.length >= minTrips,
    };
  });
  return result;
}

export async function fetchSummary(records: TripRecord[]): Promise<SpeedSummary> {
  if (records.length === 0) return EMPTY_SUMMARY;
  try {
    return await post<SpeedSummary>('/api/history/summary', { records, minTrips: MIN_TRIPS });
  } catch (err) {
    console.warn('Backend unavailable, calculating the speed summary locally.', err);
    return localSummary(records);
  }
}

export type { SpeedMode };
