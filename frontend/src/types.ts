export type LatLng = [number, number];

export type TransportMode = 'walk' | 'bike' | 'bus' | 'tram' | 'metro' | 'rail';

/** Travel profile: pace of walking / cycling and accessibility needs. */
export type Profile = 'standard' | 'slow' | 'accessible';

export interface Place {
  id: string;
  label: string;
  sublabel?: string;
  position: LatLng;
  isCurrentLocation?: boolean;
}

export interface RouteLeg {
  mode: TransportMode;
  from: string;
  to: string;
  /** Line name, e.g. "M1", "17", "175". */
  line?: string;
  durationMin: number;
  distanceM: number;
  path: LatLng[];
  /** 1-based number of the intermediate stop this leg ends at (trips with stops). */
  stop?: number;
}

/** Keep the intermediate stops as added, or let the backend reorder them for the shortest trip. */
export type StopOrder = 'given' | 'optimal';

export interface RouteOption {
  id: string;
  title: string;
  legs: RouteLeg[];
  departure: string;
  arrival: string;
  durationMin: number;
  distanceM: number;
  calories: number;
  transfers: number;
  costPln: number;
  tags: string[];
  /** Start, the intermediate stops in the order they are visited, destination (trips with stops only). */
  waypoints?: Place[];
}

/** A stop in the delay estimate. Times are Warsaw local `HH:MM:SS`. */
export interface DelayStop {
  id: string;
  name: string;
  scheduled: string;
  /** Previous stop only: when the vehicle passed it (null when not found). */
  passedAt?: string | null;
  /** Next stop only: scheduled + delay (null when the delay is not available). */
  expected?: string | null;
}

/** Detail of the `bus-delay` event = answer of `GET /api/live/delay` (see data/API.md). */
export interface BusDelayDetail {
  vehicleId: string;
  vehicle?: string;
  line?: string;
  brigade?: string;
  mode?: string;
  tripId?: string | null;
  headsign?: string | null;
  /** false = "Dane o opóźnieniu niedostępne". */
  available: boolean;
  /** Why not available: no_trip, outside_trip, no_pass_in_radius; frontend only: unknown_vehicle, backend_unavailable. */
  reason: string | null;
  /** Seconds; negative = early. Null when not available. */
  delaySec: number | null;
  /** Stop K-1, where the delay was measured. */
  prevStop: DelayStop | null;
  /** Stop K, where the delay is shown. */
  nextStop: DelayStop | null;
  radiusM?: number;
  updatedAt?: number | null;
}

/** Public transport vehicles the user can be inside of (no walking / Veturilo). */
export type VehicleMode = Exclude<TransportMode, 'walk' | 'bike'>;

export interface VehicleCandidate {
  id: string;
  mode: VehicleMode;
  /** Line name, e.g. "17", "175", "M1". */
  line: string;
  /** Direction of travel, e.g. "Annopol". Empty when unknown (live buses have no direction yet). */
  direction: string;
  /** Vehicle number from the live data. */
  vehicleNo?: string;
  /** Brigade from the live data. */
  brigade?: string;
  /** How far the vehicle is from the user, metres (RMSE of the match). */
  distanceM?: number;
  /** Chosen by hand from the list of lines, not detected. */
  manual?: boolean;
}
