import type { VehicleCandidate } from '../types';

/**
 * When is a detected vehicle "confident" (one clear match, shown as a small bar instead of the sheet)?
 *
 * Top-1 `distanceM` (the RMSE of the match) <= 60 m AND the second candidate >= 2.5x worse (or no second one).
 *
 * Tuned on the recorded live buses (`data/live/bus_track_sample.json`, the same replay as
 * `algorithms/simulation/RESULTS.md`): 600 simulated riders (GPS error 10-100 m, 1 or 3 points) and 600
 * pedestrians standing still where a bus passed 30-120 s earlier or later.
 * - The RMSE to the own bus is ~40-50 m with a good fix (the feed lags 10-20 s), ~80 m with 100 m GPS error,
 *   so 60 m keeps the good fixes and drops the vague ones.
 * - 60 m / 2.5x: 47% of riders get the bar, and the bar names the right vehicle in 97.5% of them;
 *   7.5% of the pedestrians get a (wrong) bar. Without the ratio (1.5x) the bar is right 95.9% of the time;
 *   a looser 100 m raises the pedestrian false bars to 13-18%.
 * A false bar is cheap (one line, no sheet), a wrong confident line is not, so the rule favours precision.
 */
export const CONFIDENT_MAX_RMSE_M = 60;
export const CONFIDENT_MIN_RATIO = 2.5;
/**
 * Above this top-1 RMSE nothing plausible was matched, so an automatic detection shows nothing (the bus button
 * still opens the sheet). The backend always returns the 4 nearest vehicles with no distance cut-off, so without
 * this the sheet opened for vehicles hundreds of metres away. A rider's own vehicle is ~40-50 m with a good fix and
 * ~80 m with 100 m GPS error (same replay as above), so 120 m keeps real riders and drops absurd matches.
 */
export const PLAUSIBLE_MAX_RMSE_M = 120;

/** Is the best match close enough to be a vehicle the user may be in? */
export function isPlausible(candidates: VehicleCandidate[]): boolean {
  const first = candidates[0];
  return first?.distanceM !== undefined && first.distanceM <= PLAUSIBLE_MAX_RMSE_M;
}

export function isConfident(candidates: VehicleCandidate[]): boolean {
  const [first, second] = candidates;
  if (first?.distanceM === undefined || first.distanceM > CONFIDENT_MAX_RMSE_M) return false;
  if (second?.distanceM === undefined) return second === undefined;
  return second.distanceM >= CONFIDENT_MIN_RATIO * first.distanceM;
}

/** What an automatic detection (not asked by the user) shows: nothing, the collapsed bar, or the sheet. */
export type AutoVehicleView = 'none' | 'bar' | 'sheet';

export function autoVehicleView(result: {
  candidates: VehicleCandidate[];
  offline: boolean;
  liveUnavailable?: boolean;
}): AutoVehicleView {
  if (result.offline || result.liveUnavailable || !isPlausible(result.candidates)) return 'none';
  return isConfident(result.candidates) ? 'bar' : 'sheet';
}
