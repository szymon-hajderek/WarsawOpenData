import type { Place, RouteOption, StopOrder } from '../types';
import { ROUTER_MODE, type StreetMode } from '../travel';
import { API_URL, apiUrl } from '../config';
import { BackendOfflineError } from './routes';
import { isRouteOptions } from './validate';

/**
 * Street-only trips (walking, wheelchair, stroller, own bike): `POST /api/routes` with `travel`, answered by the street
 * router behind the backend. There is no mock and no straight line here, on purpose: for a wheelchair or a stroller the
 * user must know the path was really checked for steps.
 */

/** A failure with a text the user can read. */
export class StreetRouteError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const MESSAGES: Record<number, string> = {
  // only old servers: every street mode (also stroller) is supported now
  400: 'Ten tryb nie jest jeszcze dostępny na serwerze',
  404: 'Brak trasy',
  422: 'Punkt poza zasięgiem mapy',
  503: 'Serwer tras nie działa',
};
const messageFor = (status: number) => MESSAGES[status] ?? 'Serwer tras nie działa';

/** A street trip, also through intermediate stops (the backend chains the parts and orders the stops). */
export async function fetchStreetTrip(
  { from, to, via = [], order = 'given', when }: { from: Place; to: Place; via?: Place[]; order?: StopOrder; when?: string },
  mode: StreetMode,
  signal?: AbortSignal,
): Promise<RouteOption[]> {
  if (!API_URL) throw new StreetRouteError(503, 'Ta opcja wymaga serwera tras');
  let res: Response;
  try {
    res = await fetch(apiUrl('/api/routes'), {
      signal,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, travel: ROUTER_MODE[mode], ...(via.length ? { via, order } : {}), ...(when ? { when } : {}) }),
    });
  } catch (err) {
    if (signal?.aborted) throw err;
    throw new BackendOfflineError();
  }
  if (!res.ok) throw new StreetRouteError(res.status, messageFor(res.status));
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    throw new StreetRouteError(502, messageFor(502));
  }
  if (!isRouteOptions(data)) throw new StreetRouteError(502, messageFor(502));
  if (data.length === 0) throw new StreetRouteError(404, messageFor(404));
  // one option is expected; only the first is shown
  return data.slice(0, 1);
}

/** One street path between two places. */
export async function fetchStreetRoute(from: Place, to: Place, mode: StreetMode, signal?: AbortSignal): Promise<RouteOption> {
  return (await fetchStreetTrip({ from, to }, mode, signal))[0];
}
