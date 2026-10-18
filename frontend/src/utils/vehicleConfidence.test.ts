import { describe, expect, it } from 'vitest';
import { autoVehicleView, isConfident } from './vehicleConfidence';
import type { VehicleCandidate } from '../types';

const c = (id: string, distanceM?: number): VehicleCandidate => ({ id, mode: 'bus', line: id, direction: '', distanceM });

describe('isConfident', () => {
  it('needs a close first match', () => {
    expect(isConfident([c('a', 30), c('b', 300)])).toBe(true);
    expect(isConfident([c('a', 60), c('b', 150)])).toBe(true);
    expect(isConfident([c('a', 61), c('b', 900)])).toBe(false);
  });
  it('needs the second candidate clearly worse', () => {
    expect(isConfident([c('a', 30), c('b', 74)])).toBe(false);
    expect(isConfident([c('a', 30), c('b', 75)])).toBe(true);
  });
  it('one candidate alone is confident when close', () => {
    expect(isConfident([c('a', 20)])).toBe(true);
  });
  it('no distances or no candidates: not confident', () => {
    expect(isConfident([])).toBe(false);
    expect(isConfident([c('a')])).toBe(false);
    expect(isConfident([c('a', 20), c('b')])).toBe(false);
  });
});

describe('autoVehicleView', () => {
  it('shows nothing when nothing was detected', () => {
    expect(autoVehicleView({ candidates: [], offline: false })).toBe('none');
    expect(autoVehicleView({ candidates: [c('a', 10)], offline: true })).toBe('none');
    expect(autoVehicleView({ candidates: [], offline: false, liveUnavailable: true })).toBe('none');
  });
  it('bar for one confident vehicle, the sheet for several plausible ones', () => {
    expect(autoVehicleView({ candidates: [c('a', 14), c('b', 310)], offline: false })).toBe('bar');
    expect(autoVehicleView({ candidates: [c('a', 40), c('b', 55)], offline: false })).toBe('ask');
  });
  it('shows nothing when even the best match is absurdly far (no plausible vehicle)', () => {
    expect(autoVehicleView({ candidates: [c('a', 450), c('b', 900)], offline: false })).toBe('none');
    expect(autoVehicleView({ candidates: [c('a', 61)], offline: false })).toBe('none');
    expect(autoVehicleView({ candidates: [c('a', 50), c('b', 70)], offline: false })).toBe('ask');
  });
});
