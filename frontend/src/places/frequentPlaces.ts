import type { Place } from '../types';
import { matchScore } from '../utils/placeSearch';

/**
 * Places the user searches often, learnt on the device only (localStorage, never sent anywhere).
 * Every place of a searched trip gets a point; points lose half their weight every 30 days.
 */

export interface FrequentPlace {
  id: string;
  label: string;
  sublabel?: string;
  position: Place['position'];
  /** Points at `lastAt` (before decay). */
  score: number;
  /** Epoch ms of the last search with this place. */
  lastAt: number;
}

export const STORAGE_KEY = 'frequent-places';
export const MAX_PLACES = 50;
/** A place is suggested from this many decayed points: two searches up to 30 days apart. */
export const MIN_SCORE = 1.5;
const HALF_LIFE_MS = 30 * 24 * 3600 * 1000;
/** The same place counts once per this window (filters, swap and re-runs do not inflate it). */
const DEDUP_MS = 10 * 60 * 1000;

export const decayed = (p: FrequentPlace, now: number) =>
  p.score * 0.5 ** (Math.max(0, now - p.lastAt) / HALF_LIFE_MS);

/** Adds one point to each place (the current location is skipped); keeps the best `MAX_PLACES`. */
export function recordPlaces(list: FrequentPlace[], places: Place[], now: number): FrequentPlace[] {
  const byId = new Map(list.map((p) => [p.id, p]));
  for (const place of places) {
    if (place.isCurrentLocation) continue;
    const old = byId.get(place.id);
    if (old && now - old.lastAt < DEDUP_MS) continue;
    byId.set(place.id, {
      id: place.id,
      label: place.label,
      ...(place.sublabel ? { sublabel: place.sublabel } : {}),
      position: place.position,
      score: (old ? decayed(old, now) : 0) + 1,
      lastAt: now,
    });
  }
  return [...byId.values()].sort((a, b) => decayed(b, now) - decayed(a, now)).slice(0, MAX_PLACES);
}

/** The best `n` places with at least `MIN_SCORE` points; with a query only the names that match it. */
export function topPlaces(list: FrequentPlace[], now: number, n = 3, query?: string): Place[] {
  return list
    .map((p) => ({ p, score: decayed(p, now), match: query ? matchScore(query, p.label) : 0 }))
    .filter(({ score, match }) => score >= MIN_SCORE && match !== null)
    .sort((a, b) => (a.match ?? 0) - (b.match ?? 0) || b.score - a.score)
    .slice(0, n)
    .map(({ p }) => ({ id: p.id, label: p.label, sublabel: p.sublabel, position: p.position }));
}

export function loadFrequent(): FrequentPlace[] {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (p): p is FrequentPlace =>
        typeof p?.id === 'string' &&
        typeof p.label === 'string' &&
        Array.isArray(p.position) &&
        typeof p.score === 'number' &&
        typeof p.lastAt === 'number',
    );
  } catch {
    return [];
  }
}

export function saveFrequent(list: FrequentPlace[]) {
  try {
    if (list.length) localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable */
  }
}
