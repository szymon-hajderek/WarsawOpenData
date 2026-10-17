import type { LatLng, Place } from '../types';

/**
 * Search of our own stops and Veturilo stations while typing, in the browser (same rules as
 * `algorithms/place_search.py`): case and Polish accents are ignored, and a name matches when the query is
 * the whole name (0), its start (1), the starts of its words in any order (2) or somewhere inside it (3).
 */

/** [name, lat, lon, kind] with kind 0 = stop, 1 = Veturilo station (`backend/export_places.py`). */
export type PlaceRow = [string, number, number, 0 | 1];

const EXTRA: Record<string, string> = { ł: 'l', ø: 'o', đ: 'd' };

export function fold(text: string): string {
  return text
    .toLowerCase()
    .replace(/[łøđ]/g, (c) => EXTRA[c])
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/-/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .join(' ');
}

export function matchScore(query: string, name: string): number | null {
  const q = fold(query);
  const n = fold(name);
  if (!q || !n) return null;
  if (q === n) return 0;
  if (n.startsWith(q)) return 1;
  const words = n.split(' ');
  if (q.split(' ').every((t) => words.some((w) => w.startsWith(t)))) return 2;
  if (n.includes(q)) return 3;
  return null;
}

const metres = (a: LatLng, lat: number, lon: number) => {
  const dy = (lat - a[0]) * 111320;
  const dx = (lon - a[1]) * 111320 * Math.cos((a[0] * Math.PI) / 180);
  return Math.hypot(dx, dy);
};

const KIND = ['Przystanek', 'Stacja Veturilo'];

/** The best `limit` rows for the text, as places (ids are stable for one version of the list). */
export function searchRows(rows: PlaceRow[], query: string, limit = 4, near?: LatLng): Place[] {
  const scored: { score: number; distance: number; name: string; index: number }[] = [];
  rows.forEach(([name, lat, lon], index) => {
    const score = matchScore(query, name);
    if (score === null) return;
    scored.push({ score, distance: near ? Math.round(metres(near, lat, lon)) : 0, name, index });
  });
  scored.sort((a, b) => a.score - b.score || a.distance - b.distance || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  return scored.slice(0, limit).map(({ index }) => {
    const [name, lat, lon, kind] = rows[index];
    return { id: `${kind ? 'veturilo' : 'stop'}-local-${index}`, label: name, sublabel: KIND[kind], position: [lat, lon] };
  });
}
