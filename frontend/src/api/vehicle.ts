import type { LatLng, VehicleCandidate } from '../types';

/**
 * VEHICLE DETECTION.
 *
 * `detectVehicle` answers "which public transport vehicle is the user inside of?". It sends the
 * user's last 1-3 positions (kept only in memory, one every 10 s) to the backend
 * (`POST /api/live/nearest-buses`), which compares them with the live bus positions using MSE.
 * Returns the most likely vehicle first, then up to 3 other possible ones.
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

const SAMPLE_MS = 10_000;
const MAX_POINTS = 3;

// ---------------------------------------------------------------- location buffer (memory only)

let latest: TrackPoint | null = null;
const track: TrackPoint[] = [];

if (typeof navigator !== 'undefined' && navigator.geolocation) {
  navigator.geolocation.watchPosition(
    (pos) => {
      latest = { lat: pos.coords.latitude, lon: pos.coords.longitude, time_ms: Date.now() };
      if (track.length === 0) track.push(latest);
    },
    () => {
      /* no location: detection uses the position passed in, or the fallback */
    },
    { enableHighAccuracy: true },
  );
  setInterval(() => {
    if (!latest) return;
    track.push({ ...latest, time_ms: Date.now() });
    track.splice(0, track.length - MAX_POINTS);
  }, SAMPLE_MS);
}

function currentTrack(position: LatLng | null): TrackPoint[] {
  if (track.length > 0) return [...track];
  return position ? [{ lat: position[0], lon: position[1], time_ms: Date.now() }] : [];
}

// ---------------------------------------------------------------- fallback (backend not running)

const POOL: VehicleCandidate[] = [
  { id: 'tram-17', mode: 'tram', line: '17', direction: 'Annopol' },
  { id: 'bus-175', mode: 'bus', line: '175', direction: 'Lotnisko Chopina' },
  { id: 'metro-m1', mode: 'metro', line: 'M1', direction: 'Kabaty' },
  { id: 'rail-s1', mode: 'rail', line: 'S1', direction: 'Otwock' },
  { id: 'bus-523', mode: 'bus', line: '523', direction: 'Dw. Wschodni' },
  { id: 'tram-33', mode: 'tram', line: '33', direction: 'Okęcie' },
  { id: 'metro-m2', mode: 'metro', line: 'M2', direction: 'Bemowo' },
  { id: 'bus-186', mode: 'bus', line: '186', direction: 'Wilanów' },
];

function mockCandidates(position: LatLng | null): VehicleCandidate[] {
  const start = position ? Math.abs(Math.round((position[0] + position[1]) * 1000)) % POOL.length : 0;
  return [0, 3, 5, 7].map((step) => POOL[(start + step) % POOL.length]);
}

// ---------------------------------------------------------------- API

interface NearestBusesResponse {
  candidates: { id: string; line: string; mode: 'bus'; direction: string }[];
  lines: string[];
}

export async function detectVehicle(position: LatLng | null): Promise<VehicleCandidate[]> {
  const points = currentTrack(position);
  let detail: BusPopupDetail;
  try {
    if (points.length === 0) throw new Error('no location');
    const r = await fetch('/api/live/nearest-buses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ points }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data: NearestBusesResponse = await r.json();
    detail = {
      candidates: data.candidates.map(({ id, mode, line, direction }) => ({ id, mode, line, direction })),
      lines: data.lines,
      points,
    };
  } catch (e) {
    console.warn('Bus detection unavailable, using mock data:', e);
    const candidates = mockCandidates(position);
    detail = { candidates, lines: candidates.map((c) => c.line), points };
  }
  window.dispatchEvent(new CustomEvent<BusPopupDetail>(BUS_POPUP_EVENT, { detail }));
  return detail.candidates;
}

/** Detect again with the last 1-3 positions and reopen the popup (wire a "choose my line" button to it). */
export function requestLinePopup(): void {
  window.dispatchEvent(new Event(BUS_POPUP_REQUEST_EVENT));
}
