import type { Place, RouteLeg, RouteOption } from '../types';
import { haversine, sumDistance } from '../utils/geo';

/** Most intermediate stops on one trip (the backend enforces the same limit). */
export const MAX_STOPS = 5;
const MAX_OPTIONS = 3;

const distance = (a: Place, b: Place) => haversine(a.position, b.position);

function* permutations<T>(items: T[]): Generator<T[]> {
  if (items.length <= 1) {
    yield items;
    return;
  }
  for (let i = 0; i < items.length; i++) {
    const rest = [...items.slice(0, i), ...items.slice(i + 1)];
    for (const tail of permutations(rest)) yield [items[i], ...tail];
  }
}

const pathLength = (points: Place[]) =>
  points.slice(1).reduce((sum, p, i) => sum + distance(points[i], p), 0);

/** The stops in the order that gives the shortest path start -> stops -> end (exact; ties keep the given order). */
export function bestOrder(start: Place, stops: Place[], end: Place): Place[] {
  if (stops.length < 2) return stops;
  let best = stops;
  let bestLen = pathLength([start, ...stops, end]);
  for (const perm of permutations(stops)) {
    const len = pathLength([start, ...perm, end]);
    if (len < bestLen - 1e-9) {
      best = perm;
      bestLen = len;
    }
  }
  return best;
}

function addMinutes(hhmm: string, minutes: number): string {
  const [h, m] = hhmm.split(':').map(Number);
  const total = (((h * 60 + m + minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function combine(index: number, segments: RouteOption[], waypoints: Place[]): RouteOption {
  const legs: RouteLeg[] = segments.flatMap((seg, k) =>
    seg.legs.map((leg, i) => ({
      ...leg,
      stop: k < segments.length - 1 && i === seg.legs.length - 1 ? k + 1 : undefined,
    })),
  );
  const titles = [...new Set(segments.map((s) => s.title))];
  const duration = segments.reduce((s, o) => s + o.durationMin, 0);
  return {
    id: `multi-${index}`,
    title: titles.slice(0, 3).join(' → ') + (titles.length > 3 ? '…' : ''),
    legs,
    departure: segments[0].departure,
    arrival: addMinutes(segments[0].departure, duration),
    durationMin: duration,
    distanceM: segments.reduce((s, o) => s + o.distanceM, 0),
    walkDistance: sumDistance(legs, ['walk']),
    bikeDistance: sumDistance(legs, ['bike', 'veturilo']),
    transfers: segments.reduce((s, o) => s + o.transfers, 0),
    tags: [],
    waypoints,
    waitS: segments.reduce((s, o) => s + (o.waitS ?? 0), 0),
  };
}

/**
 * Chains the n-th best option of every segment into the n-th option of the whole trip.
 * Same rules as `backend/app/routing/multi.py` (used by the local mock only).
 */
export function combineSegments(perSegment: RouteOption[][], points: Place[]): RouteOption[] {
  const sorted = perSegment.map((opts) => [...opts].sort((a, b) => a.durationMin - b.durationMin));
  if (sorted.some((opts) => opts.length === 0)) return [];

  const count = Math.min(MAX_OPTIONS, Math.max(...sorted.map((o) => o.length)));
  const seen = new Set<string>();
  const result: RouteOption[] = [];
  for (let i = 0; i < count; i++) {
    const chosen = sorted.map((opts) => opts[Math.min(i, opts.length - 1)]);
    const key = chosen.map((o) => o.id).join('|');
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(combine(result.length, chosen, points));
  }
  result.sort((a, b) => a.durationMin - b.durationMin);

  result[0]?.tags.push('Najszybsza');
  return result;
}
