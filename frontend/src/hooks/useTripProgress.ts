import { useRef } from 'react';
import { routeProgress, type TripProgress } from '../utils/progress';
import type { LatLng, RouteOption } from '../types';

/**
 * Progress of the active trip along its route. Keeps the distance reached so far (forward only) and starts
 * again from 0 when the route is replaced.
 */
export function useTripProgress(route: RouteOption | null, position: LatLng | null): TripProgress | null {
  const state = useRef<{ route: RouteOption | null; position: LatLng | null; result: TripProgress | null }>({
    route: null,
    position: null,
    result: null,
  });
  if (!route || !position) return null;
  const s = state.current;
  if (s.route !== route) {
    s.route = route;
    s.position = null;
    s.result = null;
  }
  if (s.position !== position) {
    s.result = routeProgress(route, position, s.result?.alongM ?? 0);
    s.position = position;
  }
  return s.result;
}
