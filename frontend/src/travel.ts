import type { Profile } from './types';

/**
 * How the user wants to get there: three main modes. `transit` is the normal search (public transport + Veturilo through
 * `POST /api/routes`); `walk` and `bike` are street-only trips: the same endpoint with `travel` (see `ROUTER_MODE`),
 * answered by the street router. `transit` and `walk` also take an accessibility choice (`Access`).
 */
export type TravelMode = 'transit' | 'walk' | 'bike';

export const TRAVEL_MODES: TravelMode[] = ['transit', 'walk', 'bike'];

export const TRAVEL_LABELS: Record<TravelMode, string> = {
  transit: 'Komunikacja',
  walk: 'Pieszo',
  bike: 'Rower',
};

/** Accessibility of a transit or walking search: plain, wheelchair (step-free) or stroller (steps only with rails). */
export type Access = 'standard' | 'wheelchair' | 'stroller';

export const ACCESS_OPTIONS: Access[] = ['standard', 'wheelchair', 'stroller'];

export const ACCESS_LABELS: Record<Access, string> = {
  standard: 'Zwykle',
  wheelchair: 'Wózek inwalidzki',
  stroller: 'Wózek dziecięcy',
};

/** Only public transport and walking have an accessibility choice; the own bike has none. */
export const hasAccess = (m: TravelMode) => m !== 'bike';

/** A street-only trip, keyed by what the user picked (main mode + accessibility). */
export type StreetMode = 'walk' | 'wheelchair' | 'stroller' | 'bike';

/** `travel` of `POST /api/routes` for a street-only trip. */
export const ROUTER_MODE: Record<StreetMode, 'walk' | 'accessible' | 'stroller' | 'bike'> = {
  walk: 'walk',
  wheelchair: 'accessible',
  stroller: 'stroller',
  bike: 'bike',
};

/** The street trip of a main mode + accessibility, or null for public transport. */
export function streetMode(mode: TravelMode, access: Access): StreetMode | null {
  if (mode === 'bike') return 'bike';
  if (mode === 'walk') return access === 'standard' ? 'walk' : access;
  return null;
}

/** `profile` of a transit search: wheelchair and stroller plan every walking part on that mode's step-free graph. */
export const TRANSIT_PROFILE: Record<Access, Profile> = {
  standard: 'standard',
  wheelchair: 'accessible',
  stroller: 'stroller',
};
