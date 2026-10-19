import { API_URL, apiUrl } from '../config';
import type { BusDelayDetail } from '../types';
import { isBusDelay } from './validate';

/**
 * VEHICLE DELAY.
 *
 * After the user confirms a vehicle ("Jadę tą linią"), `watchDelay` asks the backend
 * (`GET /api/live/delay`) every 10 s how late that vehicle is, and sends a `bus-delay` event on
 * `window` with `BusDelayDetail` after each answer. The delay is measured at the previous stop and
 * shown for the next one; `available: false` means "Dane o opóźnieniu niedostępne".
 * There is no UI for it yet: listen to the event to display it.
 */

export const BUS_DELAY_EVENT = 'bus-delay';

const POLL_MS = 10_000;

function unavailable(vehicleId: string, reason: string): BusDelayDetail {
  return { vehicleId, available: false, reason, delaySec: null, prevStop: null, nextStop: null };
}

export async function fetchDelay(vehicleId: string): Promise<BusDelayDetail> {
  if (!API_URL) return unavailable(vehicleId, 'backend_unavailable');
  try {
    const r = await fetch(apiUrl(`/api/live/delay?vehicle=${encodeURIComponent(vehicleId)}`));
    if (r.status === 404) return unavailable(vehicleId, 'unknown_vehicle');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data: unknown = await r.json();
    if (!isBusDelay(data)) throw new Error('Unexpected delay answer');
    return data;
  } catch (e) {
    console.warn('Delay unavailable:', e);
    return unavailable(vehicleId, 'backend_unavailable');
  }
}

/** Poll the delay of one vehicle and send `bus-delay` events. Returns a function that stops it. */
export function watchDelay(vehicleId: string): () => void {
  let stopped = false;
  const tick = async () => {
    const detail = await fetchDelay(vehicleId);
    if (!stopped) window.dispatchEvent(new CustomEvent<BusDelayDetail>(BUS_DELAY_EVENT, { detail }));
  };
  void tick();
  const timer = window.setInterval(tick, POLL_MS);
  return () => {
    stopped = true;
    window.clearInterval(timer);
  };
}
