import { API_URL, apiUrl } from '../config';
import type { LegDelay, RouteDelays, RouteOption, TransportMode } from '../types';
import { isRouteDelays } from './validate';

/**
 * LIVE DELAYS OF SUGGESTED ROUTES.
 *
 * `fetchRouteDelays` asks the backend (`POST /api/live/route-delays`) how late the buses and trams of the
 * suggested routes are, before the user boards them. The server finds the live vehicle that will run each ride
 * (line + brigade of its GTFS trip). Example data, a backend that is down or a wrong answer give `{}`: no delays shown.
 */

export const TRANSIT_MODES: TransportMode[] = ['bus', 'tram', 'metro', 'rail'];
const MAX_OPTIONS = 20;
const ON_TIME_S = 60;

export async function fetchRouteDelays(options: RouteOption[], signal?: AbortSignal): Promise<RouteDelays> {
  const body = options
    .filter((o) => o.id.startsWith('pt-'))
    .slice(0, MAX_OPTIONS)
    .map((o) => ({ id: o.id, lines: o.legs.filter((l) => TRANSIT_MODES.includes(l.mode)).map((l) => l.line ?? '') }));
  if (!API_URL || body.length === 0) return {};
  try {
    const r = await fetch(apiUrl('/api/live/route-delays'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ options: body }),
      signal,
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data: unknown = await r.json();
    if (!isRouteDelays(data)) throw new Error('unexpected answer');
    return data;
  } catch (e) {
    if (!signal?.aborted) console.warn('Route delays unavailable:', e);
    return {};
  }
}

/** Delays aligned with `option.legs` (undefined for walk / bike legs and rides without data). */
export function delaysByLeg(option: RouteOption, delays: RouteDelays): (LegDelay | undefined)[] {
  const rows = delays[option.id] ?? [];
  let transit = -1;
  return option.legs.map((leg) => {
    if (!TRANSIT_MODES.includes(leg.mode)) return undefined;
    transit += 1;
    return rows.find((r) => r.transitIndex === transit && r.available && r.delaySec !== null);
  });
}

/** "+3 min", "punktualnie", "2 min wcześniej"; "ok." first when the vehicle still runs an earlier trip. */
export function legDelayLabel(d: LegDelay): string {
  const sec = d.delaySec ?? 0;
  const min = Math.max(1, Math.round(Math.abs(sec) / 60));
  const text = Math.abs(sec) < ON_TIME_S ? 'punktualnie' : sec > 0 ? `+${min} min` : `${min} min wcześniej`;
  return d.sameTrip ? text : `ok. ${text}`;
}

/** late / early / onTime, for the colour. */
export function legDelayKind(d: LegDelay): 'late' | 'early' | 'onTime' {
  const sec = d.delaySec ?? 0;
  return Math.abs(sec) < ON_TIME_S ? 'onTime' : sec > 0 ? 'late' : 'early';
}
