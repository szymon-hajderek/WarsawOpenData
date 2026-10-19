import { fetchStations, type Station } from './stations';
import { haversine } from '../utils/geo';
import type { LatLng, Place } from '../types';

/** A point picked on the map takes the name of a stop (or Veturilo station) closer than this. */
export const PICK_STOP_RADIUS_M = 60;

/** Label of a picked point that has no stop nearby. */
export const MAP_POINT_LABEL = 'Punkt na mapie';

const KIND_LABEL: Record<string, string> = {
  bus_post: 'Przystanek autobusowy',
  tram_post: 'Przystanek tramwajowy',
  metro_platform: 'Metro',
  rail_platform: 'Peron',
  rail_station: 'Stacja kolejowa',
  veturilo: 'Stacja Veturilo',
};

/**
 * The place of a point picked on the map: the nearest stop within `PICK_STOP_RADIUS_M` (`GET /api/stations`),
 * else "Punkt na mapie" at the point. Without a backend (or when it fails) it is always the plain point.
 */
export async function placeAt(position: LatLng, signal?: AbortSignal): Promise<Place> {
  const [lat, lon] = position;
  const dLat = PICK_STOP_RADIUS_M / 111_320;
  const dLon = PICK_STOP_RADIUS_M / (111_320 * Math.cos((lat * Math.PI) / 180));
  let stations: Station[] = [];
  try {
    stations = await fetchStations([lat - dLat, lon - dLon, lat + dLat, lon + dLon], signal);
  } catch {
    // no stop name then; the point itself is still a valid place
  }
  let best: Station | null = null;
  let bestM = PICK_STOP_RADIUS_M;
  for (const s of stations) {
    const m = haversine(position, s.position);
    if (m <= bestM) {
      best = s;
      bestM = m;
    }
  }
  if (best) return { id: best.id, label: best.name, sublabel: KIND_LABEL[best.kind], position: best.position };
  const p: LatLng = [Math.round(lat * 1e6) / 1e6, Math.round(lon * 1e6) / 1e6];
  return { id: `map:${p[0]},${p[1]}`, label: MAP_POINT_LABEL, position: p };
}
