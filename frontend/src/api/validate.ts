import type { RouteOption } from '../types';

const isObject = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const isPoint = (p: unknown) =>
  Array.isArray(p) && p.length === 2 && p.every((n) => typeof n === 'number' && Number.isFinite(n));

/** `fromId` / `toId` come with the new route format: absent, `null` or a string (never a number). */
const isOptionalId = (x: unknown) => x === undefined || x === null || typeof x === 'string';
const isOptionalPoint = (x: unknown) => x === undefined || x === null || isPoint(x);

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
            (l.networkPath == null || (Array.isArray(l.networkPath) && l.networkPath.every(isPoint))) &&
            isOptionalId(l.fromId) &&
            isOptionalId(l.toId) &&
            isOptionalPoint(l.start) &&
            isOptionalPoint(l.end),
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
