import type { LatLng, VehicleCandidate } from '../types';
import { API_URL, apiUrl } from '../config';
import { isNearestBuses } from './validate';

/**
 * VEHICLE DETECTION.
 *
 * `detectVehicle` answers "which public transport vehicle is the user inside of?". It sends the
 * user's last 1-3 positions (kept only in memory, one every 10 s) to the backend
 * (`POST /api/live/nearest-buses`), which compares them with the live bus positions using MSE.
 * Returns the most likely vehicle first, then up to 3 other possible ones, and all live lines.
 *
 * After each detection a `bus-popup` event is sent on `window` with `BusPopupDetail`.
 * `requestLinePopup()` asks the app to detect again and reopen the popup (manual line choice).
 */

export interface TrackPoint {
  lat: number;
  lon: number;
  time_ms: number;
}

export interface BusPopupDetail {
  candidates: VehicleCandidate[];
  /** All lines in the live data, for choosing the line by hand. */
  lines: string[];
  /** The user's positions used for the detection (1-3). */
  points: TrackPoint[];
}

export const BUS_POPUP_EVENT = 'bus-popup';
export const BUS_POPUP_REQUEST_EVENT = 'bus-popup-request';

/** The user's track: the last 1-3 positions, or just the current one when there is no track yet. */
function trackOrPosition(track: TrackPoint[], position: LatLng | null): TrackPoint[] {
  if (track.length > 0) return track;
  return position ? [{ lat: position[0], lon: position[1], time_ms: Date.now() }] : [];
}

// ---------------------------------------------------------------- API

export interface DetectionResult {
  /** The backend is switched off, could not be reached or sent a bad answer: nothing was detected. */
  offline: boolean;
  /** The most likely vehicle first, then up to 3 other possible ones. */
  candidates: VehicleCandidate[];
  /** All lines in the live data, for choosing the line by hand. */
  lines: string[];
}

/** A line picked by hand from the list of lines. */
export function manualCandidate(line: string): VehicleCandidate {
  return { id: `manual-${line}`, mode: 'bus', line, direction: '', manual: true };
}

export async function detectVehicle(
  track: TrackPoint[],
  position: LatLng | null,
  signal?: AbortSignal,
): Promise<DetectionResult> {
  const points = trackOrPosition(track, position);
  let detail: BusPopupDetail;
  if (!API_URL) {
    return { candidates: [], lines: [], offline: true }; // the backend is switched off on purpose
  } else if (points.length === 0) {
    return { candidates: [], lines: [], offline: false }; // no location, nothing to detect
  } else {
    try {
      const r = await fetch(apiUrl('/api/live/nearest-buses'), {
        signal,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ points }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data: unknown = await r.json();
      if (!isNearestBuses(data)) throw new Error('Unexpected answer shape');
      detail = {
        candidates: data.candidates.map(({ id, mode, line, direction, vehicle, brigade, rmse_m }) => ({
          id,
          mode,
          line,
          direction,
          vehicleNo: vehicle,
          brigade,
          distanceM: rmse_m,
        })),
        lines: data.lines,
        points,
      };
    } catch (e) {
      if (signal?.aborted) throw e;
      console.warn('Bus detection unavailable:', e);
      return { candidates: [], lines: [], offline: true };
    }
  }
  window.dispatchEvent(new CustomEvent<BusPopupDetail>(BUS_POPUP_EVENT, { detail }));
  return { candidates: detail.candidates, lines: detail.lines, offline: false };
}

/** Detect again with the last 1-3 positions and reopen the popup (wire a "choose my line" button to it). */
export function requestLinePopup(): void {
  window.dispatchEvent(new Event(BUS_POPUP_REQUEST_EVENT));
}
