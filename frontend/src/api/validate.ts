import type { RouteDelays, RouteOption } from '../types';
import { SEGMENT_KINDS } from '../utils/legStyle';

const isObject = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const isPoint = (p: unknown) =>
  Array.isArray(p) && p.length === 2 && p.every((n) => typeof n === 'number' && Number.isFinite(n));

/** `fromId` / `toId` come with the new route format: absent, `null` or a string (never a number). */
const isOptionalId = (x: unknown) => x === undefined || x === null || typeof x === 'string';
const isOptionalPoint = (x: unknown) => x === undefined || x === null || isPoint(x);
const isOptionalBool = (x: unknown) => x === undefined || typeof x === 'boolean';

/** One part of a leg: a known `kind`, a non-empty `[lat, lon]` path and its length. */
const isSegment = (s: unknown) =>
  isObject(s) &&
  typeof s.kind === 'string' &&
  (SEGMENT_KINDS as readonly string[]).includes(s.kind) &&
  typeof s.lengthM === 'number' &&
  Number.isFinite(s.lengthM) &&
  s.lengthM >= 0 &&
  Array.isArray(s.path) &&
  s.path.length > 0 &&
  s.path.every(isPoint);
/** `segments` are optional; when present every one must be valid. */
const isOptionalSegments = (x: unknown) => x === undefined || (Array.isArray(x) && x.every(isSegment));

/** True when the value has the shape the UI needs: every route has legs, every leg a non-empty path. */
export function isRouteOptions(value: unknown): value is RouteOption[] {
  return (
    Array.isArray(value) &&
    value.every(
      (o) =>
        isObject(o) &&
        typeof o.id === 'string' &&
        Array.isArray(o.legs) &&
        o.legs.length > 0 &&
        Array.isArray(o.tags) &&
        o.legs.every(
          (l) =>
            isObject(l) &&
            typeof l.mode === 'string' &&
            typeof l.durationMin === 'number' &&
            typeof l.distanceM === 'number' &&
            Array.isArray(l.path) &&
            l.path.length > 0 &&
            l.path.every(isPoint) &&
            isOptionalId(l.fromId) &&
            isOptionalId(l.toId) &&
            isOptionalPoint(l.start) &&
            isOptionalPoint(l.end) &&
            isOptionalSegments(l.segments) &&
            isOptionalBool(l.approximatePath),
        ),
    )
  );
}

/** True when the route-delays answer is `option id -> [{ transitIndex, available, delaySec, sameTrip }]`. */
export function isRouteDelays(value: unknown): value is RouteDelays {
  return (
    isObject(value) &&
    Object.values(value).every(
      (rows) =>
        Array.isArray(rows) &&
        rows.every(
          (r) =>
            isObject(r) &&
            typeof r.transitIndex === 'number' &&
            typeof r.available === 'boolean' &&
            (r.delaySec === null || typeof r.delaySec === 'number') &&
            typeof r.sameTrip === 'boolean',
        ),
    )
  );
}

/** True when the nearest-buses answer has the fields `detectVehicle` reads. */
export function isNearestBuses(value: unknown): value is {
  candidates: { id: string; line: string; mode: 'bus'; direction: string; vehicle?: string; brigade?: string; rmse_m?: number }[];
  lines: string[];
} {
  return (
    isObject(value) &&
    Array.isArray(value.lines) &&
    Array.isArray(value.candidates) &&
    value.candidates.every((c) => isObject(c) && typeof c.id === 'string' && typeof c.line === 'string')
  );
}
