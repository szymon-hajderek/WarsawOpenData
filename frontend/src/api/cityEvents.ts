import { API_URL, apiUrl } from '../config';
import type { Place, RouteOption } from '../types';

// New scope needs a new opt-in: never silently reuse consent to endpoint counters.
export const CITY_SHARING_KEY = 'city-research-enabled-v1';
const pending = new Set<AbortController>();
const journeys = new WeakMap<RouteOption, string>();
const plans = new WeakMap<RouteOption, string>();
let consentRevision = 0;
export const cityConsentRevision = () => consentRevision;

export function cityConsent(): boolean {
  try { return localStorage.getItem(CITY_SHARING_KEY) === 'true'; } catch { return false; }
}

export function revokeCityConsent() {
  consentRevision++;
  pending.forEach((controller) => controller.abort());
}

export function ageGroup(age: number | null | undefined): string | null {
  if (age == null || !Number.isFinite(age) || age < 10 || age > 100) return null;
  if (age < 18) return '<18';
  if (age < 25) return '18-24';
  if (age < 35) return '25-34';
  if (age < 45) return '35-44';
  if (age < 55) return '45-54';
  if (age < 65) return '55-64';
  return '65+';
}

function storedAgeGroup() {
  try { return ageGroup(JSON.parse(localStorage.getItem('preferences') ?? '{}').base?.body?.age); }
  catch { return null; }
}

export function cityPoint(place: Place) {
  return { position: [...place.position], station_id: /^(ztm|wkd|pkp|vet):/.test(place.id) ? place.id : undefined };
}

export function journeyId(route: RouteOption): string {
  let id = journeys.get(route);
  if (!id) { id = crypto.randomUUID(); journeys.set(route, id); }
  return id;
}

export function forgetJourney(route: RouteOption) { journeys.delete(route); }
export function linkJourney(route: RouteOption, id: string) { journeys.set(route, id); }

export function cityRoute(route: RouteOption) {
  let planId = plans.get(route);
  if (!planId) { planId = crypto.randomUUID(); plans.set(route, planId); }
  return { plan_id: planId, legs: cityLegs(route), duration_min: route.durationMin, distance_m: route.distanceM, transfers: route.transfers };
}

export function cityLegs(route: RouteOption) {
  return route.legs.map((leg) => ({
    mode: leg.mode, duration_min: leg.durationMin, distance_m: leg.distanceM,
    wait_s: leg.waitS ?? undefined,
    origin: leg.start ? { position: [leg.start[1], leg.start[0]], station_id: leg.fromId ?? undefined } : undefined,
    destination: leg.end ? { position: [leg.end[1], leg.end[0]], station_id: leg.toId ?? undefined } : undefined,
  }));
}

type EventType = 'search' | 'route_selected' | 'journey_started' | 'journey_finished' | 'journey_interrupted';

/** Best effort with stable retry ID; no payloads in browser logs or persistent retry queue. */
export async function logCityEvent(type: EventType, payload: Record<string, unknown>) {
  if (!API_URL || !cityConsent()) return;
  const body = JSON.stringify({ ...payload, event_id: crypto.randomUUID(), type, age_group: storedAgeGroup() });
  const controller = new AbortController();
  pending.add(controller);
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    for (let attempt = 0; attempt < 2 && !controller.signal.aborted && cityConsent(); attempt++) {
      try {
        const response = await fetch(apiUrl('/api/city-events'), {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body,
          signal: controller.signal, keepalive: true,
        });
        if (response.ok || response.status < 500) return;
      } catch { /* City collection must never affect trip planning or recording. */ }
    }
  } finally {
    clearTimeout(timeout);
    pending.delete(controller);
  }
}
