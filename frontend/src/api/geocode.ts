import type { LatLng, Place } from '../types';
import { API_URL, apiUrl } from '../config';
import { searchRows, type PlaceRow } from '../utils/placeSearch';

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

// Bounding box of Warsaw (left, top, right, bottom).
const WARSAW_VIEWBOX = '20.85,52.37,21.28,52.10';

/** Shortest text to search: our own stops are found from 2 characters, Nominatim needs 3. */
export const MIN_QUERY = 2;
const MIN_NOMINATIM = 3;
const LOCAL_LIMIT = 4;

/** Stops and Veturilo stations of `backend/export_places.py`, loaded on first use (a separate chunk). */
async function localPlaces(query: string, near?: LatLng): Promise<Place[]> {
  const { default: rows } = await import('../data/places.json');
  return searchRows(rows as PlaceRow[], query, LOCAL_LIMIT, near);
}

/**
 * Place search, limited to Warsaw. Call it debounced.
 *
 * Uses the backend (`GET /api/geocode`: our stops and Veturilo stations, then Nominatim) when `API_URL` is set.
 * When the backend is disabled or unreachable, the list of stops and stations bundled with the app answers, and
 * Nominatim is called directly for addresses.
 * `near` (the user's position) orders equally good stops by distance.
 */
export async function searchPlaces(query: string, signal?: AbortSignal, near?: LatLng): Promise<Place[]> {
  if (API_URL) {
    try {
      const where = near ? `&lat=${near[0]}&lon=${near[1]}` : '';
      const res = await fetch(apiUrl(`/api/geocode?q=${encodeURIComponent(query)}${where}`), { signal });
      if (!res.ok) throw new Error(`Geocoding failed: ${res.status}`);
      return (await res.json()) as Place[];
    } catch (err) {
      if (signal?.aborted) throw err;
      console.warn('Backend geocode unavailable, falling back to Nominatim.', err);
    }
  }
  // No backend: our own list answers at once, Nominatim adds addresses from 3 characters on.
  const local = await localPlaces(query, near);
  if (query.trim().length < MIN_NOMINATIM) return local;
  try {
    const found = await searchPlacesNominatim(query, signal);
    const seen = new Set(local.map((p) => p.label.toLowerCase()));
    return [...local, ...found.filter((p) => !seen.has(p.label.toLowerCase()))];
  } catch (err) {
    if (signal?.aborted || local.length === 0) throw err;
    return local; // the stops we found are still a useful answer
  }
}

/** Local fallback: query OpenStreetMap Nominatim directly from the browser. */
async function searchPlacesNominatim(query: string, signal?: AbortSignal): Promise<Place[]> {
  const params = new URLSearchParams({
    format: 'jsonv2',
    q: query,
    limit: '6',
    addressdetails: '1',
    viewbox: WARSAW_VIEWBOX,
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
