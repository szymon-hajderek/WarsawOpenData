import type { LatLng } from '../types';

/** One GPS fix of the simulated user: what the phone reports and where the user really is. */
export interface RideFix {
  t: number;
  lat: number;
  lon: number;
  trueLat: number;
  trueLon: number;
  leg: number;
  vehicle: string | null;
}

export interface RideEvent {
  t: number;
  event: 'board' | 'alight';
  line: string;
  vehicle: string;
  waitedS?: number;
}

/** A candidate as `POST /api/live/nearest-buses` returns it. */
export interface RideCandidate {
  id: string;
  mode: 'bus' | 'tram';
  line: string;
  direction: string;
  vehicle: string;
  brigade: string;
  rmse_m: number;
}

export interface RideDetection {
  t: number;
  vehicle: string;
  candidates: RideCandidate[];
}

/** The answer of `POST /api/sim/ride`: the whole ride, played back by the demo. */
export interface Ride {
  ok: boolean;
  reason: string;
  start: number;
  end: number;
  plan: { mode: string; line: string | null; path: LatLng[] }[];
  fixes: RideFix[];
  events: RideEvent[];
  detections: RideDetection[];
}

export interface RideSample {
  /** Where the user really is. */
  truth: LatLng;
  /** What the phone reports (with GPS error). */
  gps: LatLng;
  leg: number;
  vehicle: string | null;
  /** The latest vehicle detection at this time; null before the first one. */
  detection: RideDetection | null;
  /** The last board / alight event at this time. */
  event: RideEvent | null;
}

/** Seconds from the start to the last fix. */
export const rideDuration = (ride: Ride): number =>
  ride.fixes.length ? ride.fixes[ride.fixes.length - 1].t - ride.start : 0;

const lerp = (a: number, b: number, f: number) => a + (b - a) * f;

/** The state of the ride `elapsed` seconds after its start: position between two fixes, leg, latest detection. */
export function sampleRide(ride: Ride, elapsed: number): RideSample | null {
  const fixes = ride.fixes;
  if (fixes.length === 0) return null;
  const t = ride.start + elapsed;
  let i = 0;
  while (i < fixes.length - 1 && fixes[i + 1].t <= t) i++;
  const a = fixes[i];
  const b = fixes[Math.min(i + 1, fixes.length - 1)];
  const f = b.t > a.t ? Math.min(1, Math.max(0, (t - a.t) / (b.t - a.t))) : 0;
  const riding = a.vehicle !== null && a.vehicle === b.vehicle; // between vehicles the fixes jump to the vehicle
  const g = riding || a.leg === b.leg ? f : 0;
  const detection = [...ride.detections].reverse().find((d) => d.t <= t) ?? null;
  const event = [...ride.events].reverse().find((e) => e.t <= t) ?? null;
  return {
    truth: [lerp(a.trueLat, b.trueLat, g), lerp(a.trueLon, b.trueLon, g)],
    gps: [lerp(a.lat, b.lat, g), lerp(a.lon, b.lon, g)],
    leg: a.leg,
    vehicle: a.vehicle,
    detection: a.vehicle ? detection : null,
    event,
  };
}

