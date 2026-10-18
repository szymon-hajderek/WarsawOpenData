import type { RouteSearchBody } from '../preferences/model';
import type { Place, Profile, RouteOption, StopOrder } from '../types';
import { API_URL, apiUrl } from '../config';
import { isRouteOptions } from './validate';

/** Most intermediate stops on one trip (the backend enforces the same limit). */
export const MAX_STOPS = 5;

/**
 * ROUTING SERVICE.
 *
 * `fetchRouteOptions` is the single seam between the UI and the backend. It calls
 * the FastAPI backend (`POST /api/routes`). There is no in-browser mock: when the backend is
 * switched off (`VITE_API_URL=""`) or unreachable, the search fails with `BackendOfflineError`.
 */
export interface RouteQuery {
  from: Place;
  to: Place;
  profile: Profile;
  /** Intermediate stops (at most `MAX_STOPS`). */
  via?: Place[];
  /** Keep the stops as given, or reorder them for the shortest trip (start and destination stay fixed). */
  order?: StopOrder;
  /** Pace, transfers, excluded areas and body data. Omitted fields keep the backend defaults. */
  search?: RouteSearchBody;
  /** Warsaw local departure, ISO datetime or `HH:MM`. Empty = now (the demo sends the simulated time). */
  when?: string;
}

export interface RouteResult {
  options: RouteOption[];
}

/** The backend could not be reached or sent an answer we cannot use (so the user is told, no made-up routes are shown). */
export class BackendOfflineError extends Error {
  constructor() {
    super('Backend unavailable');
  }
}

/** The backend answered, but refused the query (4xx): not a connection problem. */
class HttpError extends Error {
  constructor(readonly status: number) {
    super(`Routing failed: ${status}`);
  }
}

export async function fetchRouteOptions(query: RouteQuery, signal?: AbortSignal): Promise<RouteResult> {
  const { from, to, profile } = query;
  const via = query.via ?? [];
  const order = query.order ?? 'given';
  if (!API_URL) throw new BackendOfflineError(); // the backend is switched off on purpose
  try {
    const res = await fetch(apiUrl('/api/routes'), {
      signal,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, profile, ...(via.length ? { via, order } : {}), ...(query.when ? { when: query.when } : {}), ...query.search }),
    });
    if (!res.ok) throw new HttpError(res.status);
    const data: unknown = await res.json();
    if (!isRouteOptions(data)) throw new Error('Routing answer has an unexpected shape');
    return { options: data };
  } catch (err) {
    if (signal?.aborted) throw err;
    if (err instanceof HttpError && err.status < 500) throw err;
    console.warn('Backend unavailable.', err);
    throw new BackendOfflineError();
  }
}
