import { API_URL, apiUrl } from '../config';
import type { Place, RouteOption } from '../types';

export interface JourneySelection {
  route?: RouteOption;
  from: Place;
  to: Place;
}

export interface JourneyPoint {
  id: string;
  position: [number, number];
  isCurrentLocation: boolean;
}

export interface JourneySubmission {
  token: string;
  from: JourneyPoint;
  to: JourneyPoint;
}

/** Capture only endpoint references, never labels, addresses or the full route/track. */
export function journeySubmission(selection: JourneySelection): JourneySubmission {
  const point = (place: Place): JourneyPoint => ({
    id: place.id,
    position: [...place.position],
    isCurrentLocation: place.isCurrentLocation === true,
  });
  return { token: crypto.randomUUID(), from: point(selection.from), to: point(selection.to) };
}

/** Best effort: one retry with the same token. Consent revocation aborts both attempts. */
export async function logJourney(body: JourneySubmission, signal: AbortSignal): Promise<boolean> {
  if (!API_URL) return false;
  for (let attempt = 0; attempt < 2 && !signal.aborted; attempt++) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal.addEventListener('abort', abort, { once: true });
    const timeout = setTimeout(abort, 5000);
    try {
      const res = await fetch(apiUrl('/api/journeys'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (res.ok) return true;
      if (res.status < 500) return false;
    } catch {
      // Do not log the payload or make statistics errors affect the user's journey.
    } finally {
      clearTimeout(timeout);
      signal.removeEventListener('abort', abort);
    }
  }
  return false;
}
