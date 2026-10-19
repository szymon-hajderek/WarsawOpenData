import type { LatLng, Place } from '../types';
import { API_URL, apiUrl } from '../config';
import { fold, looksLikeAddress, searchRows, type PlaceRow } from '../utils/placeSearch';

interface NominatimItem {
  place_id: number;
  osm_type?: 'node' | 'way' | 'relation';
  osm_id?: number;
  lat: string;
  lon: string;
  name?: string;
  display_name: string;
  address?: Record<string, string>;
}

// The ZTM area (left, top, right, bottom) = the routing area, backend `config.BBOX`: Warsaw and the suburbs
// ZTM serves (e.g. Piaseczno). Keep the two in sync.
export const VIEWBOX = '20.57,52.51,21.48,51.91';

/** Shortest text to search: our own places are found from 2 characters, Nominatim needs 3. */
export const MIN_QUERY = 2;
const MIN_NOMINATIM = 3;
const LOCAL_LIMIT = 5;
/** Extra wait before asking Nominatim (slow, ~1 request/s): only once the user stops typing. */
export const NOMINATIM_DELAY_MS = 350;

/** Well-known places, stops and Veturilo stations of `backend/export_places.py`, loaded on first use (a separate chunk). */
async function localPlaces(query: string, near?: LatLng): Promise<Place[]> {
  const { default: rows } = await import('../data/places.json');
  return searchRows(rows as PlaceRow[], query, LOCAL_LIMIT, near);
}

async function backendGeocode(
  query: string,
  source: 'local' | 'nominatim',
  signal?: AbortSignal,
  near?: LatLng,
): Promise<Place[]> {
  const where = near ? `&lat=${near[0]}&lon=${near[1]}` : '';
  const res = await fetch(apiUrl(`/api/geocode?q=${encodeURIComponent(query)}&source=${source}${where}`), { signal });
  if (!res.ok) throw new Error(`Geocoding failed: ${res.status}`);
  return (await res.json()) as Place[];
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason);
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(signal.reason);
    });
  });
}

/**
 * Our places first, then Nominatim's (a place already listed is not repeated). For a street address
 * ("Marszałkowska 1") Nominatim's come first: it is the source for addresses. Same rule as the backend.
 */
export function mergePlaces(query: string, local: Place[], remote: Place[]): Place[] {
  const seen = new Set(local.map((p) => fold(p.label)));
  const extra = remote.filter((p) => !seen.has(fold(p.label)));
  return looksLikeAddress(query) ? [...extra, ...local] : [...local, ...extra];
}

/**
 * Place search, limited to the ZTM area (Warsaw and its suburbs). Call it debounced.
 *
 * Two steps. First our own places (well-known places, stops, Veturilo stations): a few ms on the backend, or the
 * bundled list when the backend is disabled or unreachable; they are handed to `onLocal` at once. Then, from
 * 3 characters and after `NOMINATIM_DELAY_MS` more without a new query (abort `signal` to cancel), Nominatim for
 * addresses and other places: through the backend (`GET /api/geocode?source=...`, cached and rate limited there),
 * or directly without it. Resolves with the merged list. `near` (the user's position) orders equally good places
 * by distance.
 */
export async function searchPlaces(
  query: string,
  signal?: AbortSignal,
  near?: LatLng,
  onLocal?: (places: Place[]) => void,
): Promise<Place[]> {
  let backend = Boolean(API_URL);
  let local: Place[] = [];
  if (backend) {
    try {
      local = await backendGeocode(query, 'local', signal, near);
    } catch (err) {
      if (signal?.aborted) throw err;
      console.warn('Backend geocode unavailable, searching the bundled list and Nominatim.', err);
      backend = false;
    }
  }
  if (!backend) local = await localPlaces(query, near);
  if (query.trim().length < MIN_NOMINATIM) return local;
  onLocal?.(local);

  await wait(NOMINATIM_DELAY_MS, signal);
  try {
    const remote = backend
      ? await backendGeocode(query, 'nominatim', signal, near)
      : await searchPlacesNominatim(query, signal);
    return mergePlaces(query, local, remote);
  } catch (err) {
    if (signal?.aborted) throw err;
    return local; // Nominatim failed or was rate limited: our places are still a useful answer
  }
}

/** Local fallback: query OpenStreetMap Nominatim directly from the browser. */
async function searchPlacesNominatim(query: string, signal?: AbortSignal): Promise<Place[]> {
  const params = new URLSearchParams({
    format: 'jsonv2',
    q: query,
    limit: '6',
    addressdetails: '1',
    viewbox: VIEWBOX,
    bounded: '1',
    countrycodes: 'pl',
    'accept-language': 'pl',
  });
  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, { signal });
  if (!res.ok) throw new Error(`Geocoding failed: ${res.status}`);
  const items: NominatimItem[] = await res.json();

  const places = items.filter((item) => item.osm_type && item.osm_id).map((item) => {
    const a = item.address ?? {};
    const street = [a.road, a.house_number].filter(Boolean).join(' ');
    const label = item.name || street || item.display_name.split(',')[0];
    const area = a.suburb || a.neighbourhood || a.city_district || a.city || a.town;
    const sublabel = [item.name && street ? street : undefined, area].filter(Boolean).join(', ');
    return {
      id: `osm:${item.osm_type}:${item.osm_id}`,
      label,
      sublabel: sublabel || undefined,
      position: [parseFloat(item.lat), parseFloat(item.lon)] as [number, number],
    };
  });

  // Nominatim often returns the same place several times (node + way + relation).
  const seen = new Set<string>();
  return places.filter((p) => {
    const key = `${p.label}|${p.sublabel ?? ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
