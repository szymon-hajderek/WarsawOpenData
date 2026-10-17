/** A trip as the device keeps it: no coordinates, only distance, moving time and speed. */
export type SpeedMode = 'walking' | 'cycling' | 'wheelchair';

export interface TripRecord {
  mode: SpeedMode;
  distanceM: number;
  durationS: number;
  kmh: number;
  /** ISO date-time of the trip. */
  at: string;
}

export interface ModeSummary {
  trips: number;
  distanceKm: number;
  avgKmh: number | null;
  medianKmh: number | null;
  /** Enough trips to use the average as the speed setting. */
  enough: boolean;
}

export type SpeedSummary = Record<SpeedMode, ModeSummary>;

export interface TrackPoint {
  lat: number;
  lon: number;
  /** Seconds. */
  t: number;
}

export const MIN_TRIPS = 5;
export const MAX_RECORDS = 200;

export const EMPTY_SUMMARY: SpeedSummary = {
  walking: { trips: 0, distanceKm: 0, avgKmh: null, medianKmh: null, enough: false },
  cycling: { trips: 0, distanceKm: 0, avgKmh: null, medianKmh: null, enough: false },
  wheelchair: { trips: 0, distanceKm: 0, avgKmh: null, medianKmh: null, enough: false },
};
