/**
 * How the user wants to get there. `transit` is the normal search (public transport + Veturilo through
 * `POST /api/routes`); the others are street-only trips: the same endpoint with `travel` (see `ROUTER_MODE`), answered by the street router.
 */
export type TravelMode = 'transit' | 'walk' | 'wheelchair' | 'stroller' | 'bike';
export type StreetMode = Exclude<TravelMode, 'transit'>;

export const TRAVEL_MODES: TravelMode[] = ['transit', 'walk', 'wheelchair', 'stroller', 'bike'];

export const TRAVEL_LABELS: Record<TravelMode, string> = {
  transit: 'Komunikacja',
  walk: 'Pieszo',
  wheelchair: 'Wózek inwalidzki',
  stroller: 'Wózek dziecięcy',
  bike: 'Własny rower',
};

/** `travel` of `POST /api/routes` for a street-only trip. */
export const ROUTER_MODE: Record<StreetMode, 'walk' | 'accessible' | 'stroller' | 'bike'> = {
  walk: 'walk',
  wheelchair: 'accessible',
  stroller: 'stroller',
  bike: 'bike',
};

export const isStreetMode = (m: TravelMode): m is StreetMode => m !== 'transit';
