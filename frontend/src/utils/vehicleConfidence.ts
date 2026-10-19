import type { VehicleCandidate } from '../types';

/**
 * When is a detected vehicle "confident" (the bar says "Wykryliśmy, że jedziesz linią 131" instead of asking)?
 *
 * The second candidate is >= 2.5x worse than the first (or there is no second one). There is no distance limit:
 * the best match is always offered (user decision after the field test, where the feed's lag pushed the own tram
 * over the old 60 m limit and nothing was shown). The backend moves each vehicle to the time of the user's points
 * (`algorithms/nearest_buses.py`), so the own vehicle usually matches within ~10-60 m.
 */
export const CONFIDENT_MIN_RATIO = 2.5;

/** Is there a vehicle to offer at all? */
export function isPlausible(candidates: VehicleCandidate[]): boolean {
  return candidates[0]?.distanceM !== undefined;
}

export function isConfident(candidates: VehicleCandidate[]): boolean {
  const [first, second] = candidates;
  if (first?.distanceM === undefined) return false;
  if (second?.distanceM === undefined) return second === undefined;
  return second.distanceM >= CONFIDENT_MIN_RATIO * first.distanceM;
}

/**
 * What an automatic detection (not asked by the user) shows. Never the big sheet: always a small collapsed bar the
 * user can expand. 'bar' = one confident vehicle ("Wykryliśmy, że jedziesz linią 131"), 'ask' = a plausible vehicle
 * without certainty ("Czy jedziesz tym pojazdem? Tramwaj 26"), 'none' = nothing to offer (no candidates, no location, no
 * live data, offline). Speed is not used: a bus standing in a jam at the
 * user's position (RMSE ~0) is the best possible match.
 */
export type AutoVehicleView = 'none' | 'bar' | 'ask';

export function autoVehicleView(result: {
  candidates: VehicleCandidate[];
  offline: boolean;
  liveUnavailable?: boolean;
}): AutoVehicleView {
  if (result.offline || result.liveUnavailable || !isPlausible(result.candidates)) return 'none';
  return isConfident(result.candidates) ? 'bar' : 'ask';
}
