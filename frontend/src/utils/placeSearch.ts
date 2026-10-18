import type { LatLng, Place } from '../types';

/**
 * Search of well-known places, our stops and Veturilo stations while typing, in the browser. TypeScript twin of
 * `algorithms/place_search.py` (same rules, keep both in sync):
 * - case and Polish accents are ignored; text splits into words of letters and of digits ("DS2" = "ds 2");
 * - abbreviations match their full form both ways ("pl" = "plac", "ds" = "dom studenta", "uw" = "uniwersytet
 *   warszawski"); "nr", "ul", "ulica" in the query are ignored;
 * - a number matches only the same number, other words match the start of a word of the name.
 * Quality (lower is better): 0 the whole name, 1 its start (or the whole name with abbreviations written out),
 * 2 every query word is a whole word (any order), 3 every query word starts a word (any order), 4 inside the name.
 */

/**
 * [name, lat, lon, kind] with kind 0 = stop, 1 = Veturilo station, or [name, lat, lon, 2, sublabel, aliases] for a
 * well-known place (`backend/export_places.py`).
 */
export type PlaceRow = [string, number, number, 0 | 1] | [string, number, number, 2, string, string[]];

const ABBREVIATIONS: Record<string, string[][]> = {
  ds: [['dom', 'studenta'], ['dom', 'studencki']],
  pl: [['plac']],
  al: [['aleja'], ['aleje'], ['alei']],
  dw: [['dworzec']],
  os: [['osiedle']],
  uw: [['uniwersytet', 'warszawski'], ['uniwersytetu', 'warszawskiego']],
  pw: [['politechnika', 'warszawska'], ['politechniki', 'warszawskiej']],
};
const STOPWORDS = new Set(['nr', 'ul', 'ulica']);
const ADDRESS = /^.*[a-z]{2}.*[a-z.]\s+\d+[a-z]?(\/\d+[a-z]?)?$/;

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

/** Folded words of letters and of digits: "DS2 UW" -> ["ds", "2", "uw"]. */
export function words(text: string): string[] {
  return fold(text).match(/[a-z]+|\d+/g) ?? [];
}

const isDigits = (w: string) => /^\d+$/.test(w);
const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((w, i) => w === b[i]);

function canonical(ws: string[]): string[] {
  return ws.flatMap((w) => (ABBREVIATIONS[w] ? ABBREVIATIONS[w][0] : [w]));
}

function expanded(ws: string[]): Set<string> {
  const out = new Set(ws);
  for (const [short, forms] of Object.entries(ABBREVIATIONS)) {
    if (ws.includes(short)) forms.forEach((form) => form.forEach((w) => out.add(w)));
    for (const form of forms) {
      for (let i = 0; i + form.length <= ws.length; i++) {
        if (sameList(ws.slice(i, i + form.length), form)) out.add(short);
      }
    }
  }
  return out;
}

interface Prepared {
  folded: string;
  ws: string[];
  canon: string[];
  expanded: Set<string>;
}

interface Query {
  folded: string;
  tokens: string[];
  canon: string[];
}

function prepareText(text: string): Prepared {
  const ws = words(text);
  return { folded: fold(text), ws, canon: canonical(ws), expanded: expanded(ws) };
}

function toQuery(query: string): Query | null {
  const ws = words(query);
  const kept = ws.filter((w) => !STOPWORDS.has(w));
  const tokens = kept.length ? kept : ws;
  if (!tokens.length) return null;
  return { folded: fold(query), tokens, canon: canonical(tokens) };
}

const hits = (token: string, word: string) => (isDigits(token) ? word === token : word.startsWith(token));

function score(q: Query, p: Prepared): number | null {
  if (!p.canon.length) return null;
  if (sameList(q.tokens, p.ws)) return 0;
  if (sameList(q.canon, p.canon)) return 1;
  const n = q.canon.length;
  if (n <= p.canon.length && sameList(q.canon.slice(0, -1), p.canon.slice(0, n - 1)) && hits(q.canon[n - 1], p.canon[n - 1])) {
    return 1;
  }
  const all = [...p.expanded];
  if (q.tokens.every((t) => p.expanded.has(t))) return 2;
  if (q.tokens.every((t) => all.some((w) => hits(t, w)))) return 3;
  if (p.folded.includes(q.folded) && !q.tokens.some(isDigits)) return 4; // "2" must not be found inside "21"
  return null;
}

function best(q: Query, prepared: Prepared[]): number | null {
  let result: number | null = null;
  for (const p of prepared) {
    const s = score(q, p);
    if (s !== null && (result === null || s < result)) result = s;
  }
  return result;
}

/** 0..4 (see above) for the best of the name and its aliases; null = no match. */
export function matchScore(query: string, name: string, aliases: string[] = []): number | null {
  const q = toQuery(query);
  if (!q || !fold(name)) return null;
  return best(q, [name, ...aliases].map(prepareText));
}

/** A street and a house number ("Marszałkowska 1"): Nominatim, not our stop list, is the source for it. */
export function looksLikeAddress(query: string): boolean {
  const ws = words(query);
  return ADDRESS.test(fold(query)) && !ws.some((w) => STOPWORDS.has(w)) && !ws.includes('ds');
}

const metres = (a: LatLng, lat: number, lon: number) => {
  const dy = (lat - a[0]) * 111320;
  const dx = (lon - a[1]) * 111320 * Math.cos((a[0] * Math.PI) / 180);
  return Math.hypot(dx, dy);
};

const KIND = ['Przystanek', 'Stacja Veturilo'];

// Match data of a list, computed once per list (the bundled list has a few thousand rows).
const preparedRows = new WeakMap<PlaceRow[], Prepared[][]>();

function prepareRows(rows: PlaceRow[]): Prepared[][] {
  let prepared = preparedRows.get(rows);
  if (!prepared) {
    prepared = rows.map((row) => [row[0], ...(row[3] === 2 ? row[5] : [])].map(prepareText));
    preparedRows.set(rows, prepared);
  }
  return prepared;
}

/**
 * The best `limit` rows for the text, as places (ids are stable for one version of the list). Equal matches are
 * ordered: well-known places first, then by distance from `near`, then by name.
 */
export function searchRows(rows: PlaceRow[], query: string, limit = 5, near?: LatLng): Place[] {
  const q = toQuery(query);
  if (!q) return [];
  const prepared = prepareRows(rows);
  const scored: { score: number; rank: number; distance: number; name: string; index: number }[] = [];
  rows.forEach(([name, lat, lon, kind], index) => {
    const s = best(q, prepared[index]);
    if (s === null) return;
    const distance = near ? Math.round(metres(near, lat, lon)) : 0;
    scored.push({ score: s, rank: kind === 2 ? 0 : 1, distance, name, index });
  });
  scored.sort(
    (a, b) =>
      a.score - b.score || a.rank - b.rank || a.distance - b.distance || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0),
  );
  return scored.slice(0, limit).map(({ index }) => {
    const row = rows[index];
    const [name, lat, lon] = row;
    if (row[3] === 2) return { id: `place-local-${index}`, label: name, sublabel: row[4], position: [lat, lon] };
    return { id: `${row[3] ? 'veturilo' : 'stop'}-local-${index}`, label: name, sublabel: KIND[row[3]], position: [lat, lon] };
  });
}
