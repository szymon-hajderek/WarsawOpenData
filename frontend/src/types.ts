export type LatLng = [number, number];

/** GPS order `[lon, lat]` (the start and end of a leg). */
export type LonLat = [number, number];

/** `bike` = the rider's own bike, `veturilo` = a rented Veturilo bike. */
export type TransportMode = 'walk' | 'bike' | 'veturilo' | 'bus' | 'tram' | 'metro' | 'rail';

/** Travel profile: pace of walking / cycling and accessibility needs. */
export type Profile = 'standard' | 'slow' | 'accessible' | 'stroller';

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
  /** Where the leg starts and ends, `[lon, lat]`. */
  start?: LonLat;
  end?: LonLat;
  path: LatLng[];
  /** 1-based number of the intermediate stop this leg ends at (trips with stops). */
  stop?: number;
  /** `GET /api/stations` id of the stop / station at each end (`ztm:435102`, `vet:14083304`), `null` for a place that is not one. */
  fromId?: string | null;
  toId?: string | null;
  /** `[lat, lon]` where a street leg boards an elevator / starts a flight of steps. */
  elevators?: LatLng[] | null;
  steps?: LatLng[] | null;
  /** Transit legs: seconds waited at the boarding stop (`fromId`) before departure. */
  waitS?: number | null;
  /** Transit legs: the GTFS trip id. */
  tripId?: string | null;
  /** Consecutive parts of one kind that cover the whole `path` (street legs; optional). */
  segments?: LegSegment[];
  /** True when GTFS has no shape for the trip and `path` only joins the stops in order (drawn dashed). */
  approximatePath?: boolean;
}

/** `ride` = bike ridden, `push` = bike pushed, `metro_access` = the walk down to a metro platform. */
export type SegmentKind = 'ride' | 'push' | 'walk' | 'steps' | 'elevator' | 'metro_access';

export interface LegSegment {
  kind: SegmentKind;
  path: LatLng[];
  lengthM: number;
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
  /** Metres walked (including a pushed bike) and ridden (own bike + Veturilo). */
  walkDistance: number;
  bikeDistance: number;
  transfers: number;
  tags: string[];
  /** Start, the intermediate stops in the order they are visited, destination (trips with stops only). */
  waypoints?: Place[];
  /** Total standing time, seconds: waiting at stops plus signals, crossings, elevators. */
  waitS?: number | null;
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
export type VehicleMode = Exclude<TransportMode, 'walk' | 'bike' | 'veturilo'>;

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
