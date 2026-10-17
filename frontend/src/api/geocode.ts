import type { Place } from '../types';
import { API_URL } from '../config';

interface NominatimItem {
  place_id: number;
  lat: string;
  lon: string;
  name?: string;
  display_name: string;
  address?: Record<string, string>;
}

// Bounding box of Warsaw (left, top, right, bottom).
const WARSAW_VIEWBOX = '20.85,52.37,21.28,52.10';

/**
 * Place search, limited to Warsaw. Call it debounced.
 *
 * Uses the backend proxy (`GET /api/geocode`) when `API_URL` is set, and falls back
 * to calling Nominatim directly when the backend is disabled or unreachable.
 */
export async function searchPlaces(query: string): Promise<Place[]> {
  if (API_URL) {
    try {
      const res = await fetch(`${API_URL}/api/geocode?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error(`Geocoding failed: ${res.status}`);
      return (await res.json()) as Place[];
    } catch (err) {
      console.warn('Backend geocode unavailable, falling back to Nominatim.', err);
    }
  }
  return searchPlacesNominatim(query);
}

/** Local fallback: query OpenStreetMap Nominatim directly from the browser. */
async function searchPlacesNominatim(query: string): Promise<Place[]> {
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
  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`);
  if (!res.ok) throw new Error(`Geocoding failed: ${res.status}`);
  const items: NominatimItem[] = await res.json();

  const places = items.map((item) => {
    const a = item.address ?? {};
    const street = [a.road, a.house_number].filter(Boolean).join(' ');
    const label = item.name || street || item.display_name.split(',')[0];
    const area = a.suburb || a.neighbourhood || a.city_district || a.city || a.town;
    const sublabel = [item.name && street ? street : undefined, area].filter(Boolean).join(', ');
    return {
      id: `osm-${item.place_id}`,
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
