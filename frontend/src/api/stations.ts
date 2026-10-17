import type { LatLng } from '../types';
import { API_URL, apiUrl } from '../config';

/**
 * The stop overlay: `GET /api/stations` (data/API.md, "Stations (StationLocations)"). Each location is a bus / tram
 * post, a metro or rail platform, a rail station or a Veturilo station, at its mapped position.
 */
export type StationKind = 'bus_post' | 'tram_post' | 'metro_platform' | 'rail_platform' | 'rail_station' | 'veturilo';

export interface Station {
  id: string;
  kind: StationKind | string;
  name: string;
  /** The position to draw (`position` of the answer, as `[lat, lon]`). */
  position: LatLng;
  /** Metro: the station's entrances (where the walk goes down), as `[lat, lon]`. */
  entrances: LatLng[];
}

const isObject = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const isNum = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

/** Reads one location of the answer; `null` when it lacks an id, a name or a position. */
export function parseStation(raw: unknown): Station | null {
  if (!isObject(raw) || typeof raw.id !== 'string' || typeof raw.name !== 'string' || typeof raw.kind !== 'string') return null;
  const p = raw.position;
  if (!isObject(p) || !isNum(p.lat) || !isNum(p.lon)) return null;
  const entrances: LatLng[] = Array.isArray(raw.entrances)
    ? raw.entrances.flatMap((e) => (isObject(e) && isNum(e.lat) && isNum(e.lon) ? [[e.lat, e.lon] as LatLng] : []))
    : [];
  return { id: raw.id, kind: raw.kind, name: raw.name, position: [p.lat, p.lon], entrances };
}

/** Stations inside a box (`min_lat,min_lon,max_lat,max_lon`). Empty without a backend: there are no made-up stops. */
export async function fetchStations(bbox: [number, number, number, number], signal?: AbortSignal): Promise<Station[]> {
  if (!API_URL) return [];
  const res = await fetch(apiUrl(`/api/stations?bbox=${bbox.join(',')}`), { signal });
  if (!res.ok) throw new Error(`Stations failed: ${res.status}`);
  const data: unknown = await res.json();
  if (!Array.isArray(data)) throw new Error('Stations answer has an unexpected shape');
  return data.flatMap((raw) => {
    const s = parseStation(raw);
    return s ? [s] : [];
  });
}

/** One station by its id (`ztm:435102`), or `null` when the server does not know it. */
export async function fetchStation(id: string, signal?: AbortSignal): Promise<Station | null> {
  if (!API_URL) return null;
  const res = await fetch(apiUrl(`/api/stations/${encodeURIComponent(id)}`), { signal });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Station failed: ${res.status}`);
  return parseStation(await res.json());
}
