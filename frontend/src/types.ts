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
