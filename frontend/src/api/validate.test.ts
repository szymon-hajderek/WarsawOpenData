import { describe, expect, it } from 'vitest';
import { isBusDelay, isNearestBuses, isRouteOptions } from './validate';

const leg = { mode: 'walk', durationMin: 5, distanceM: 300, path: [[52.2, 21.0], [52.21, 21.01]] };
const option = { id: 'walk', legs: [leg], tags: [] };

describe('isRouteOptions', () => {
  it('accepts a route with legs and paths', () => {
    expect(isRouteOptions([option])).toBe(true);
    expect(isRouteOptions([])).toBe(true);
  });

  it('rejects a route without legs', () => {
    expect(isRouteOptions([{ ...option, legs: [] }])).toBe(false);
  });

  it('rejects a leg with an empty or broken path', () => {
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, path: [] }] }])).toBe(false);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, path: [[1, 'x']] }] }])).toBe(false);
  });

  it('accepts legs with or without fromId / toId and start / end', () => {
    expect(isRouteOptions([option])).toBe(true);
    const withIds = { ...leg, fromId: 'ztm:435102', toId: null, start: [21.0, 52.2], end: [21.01, 52.21] };
    expect(isRouteOptions([{ ...option, legs: [withIds] }])).toBe(true);
  });

  it('rejects a numeric fromId and a broken start', () => {
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, fromId: 5 }] }])).toBe(false);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, toId: 7 }] }])).toBe(false);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, start: [1] }] }])).toBe(false);
  });

  it('accepts legs with and without segments / approximatePath', () => {
    const segments = [
      { kind: 'push', path: [[52.2, 21.0], [52.201, 21.001]], lengthM: 120 },
      { kind: 'ride', path: [[52.201, 21.001], [52.21, 21.01]], lengthM: 900 },
    ];
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, mode: 'bike', segments }] }])).toBe(true);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, mode: 'bus', approximatePath: true }] }])).toBe(true);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, mode: 'bus', approximatePath: false }] }])).toBe(true);
  });

  it('rejects approximatePath that is not a boolean', () => {
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, approximatePath: 'yes' }] }])).toBe(false);
  });

  it('rejects a segment with a bad kind, path or length', () => {
    const withSegment = (s: object) => [{ ...option, legs: [{ ...leg, segments: [s] }] }];
    expect(isRouteOptions(withSegment({ kind: 'fly', path: [[52.2, 21.0]], lengthM: 1 }))).toBe(false);
    expect(isRouteOptions(withSegment({ kind: 'ride', path: [], lengthM: 1 }))).toBe(false);
    expect(isRouteOptions(withSegment({ kind: 'ride', path: [[52.2, 'x']], lengthM: 1 }))).toBe(false);
    expect(isRouteOptions(withSegment({ kind: 'ride', path: [[52.2, 21.0]] }))).toBe(false);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, segments: 'ride' }] }])).toBe(false);
  });

  it('accepts elevators / steps, the waits and tripId', () => {
    const street = { ...leg, elevators: [[52.205, 21.005]], steps: [] };
    const ride = { ...leg, mode: 'bus', waitS: 240, tripId: '3/1/20' };
    expect(isRouteOptions([{ ...option, waitS: 300.5, legs: [street, ride] }])).toBe(true);
    expect(isRouteOptions([{ ...option, waitS: 0, legs: [{ ...ride, waitS: 0 }] }])).toBe(true);
  });

  it('rejects bad elevators / steps, waits and tripId', () => {
    const withLeg = (extra: object) => [{ ...option, legs: [{ ...leg, ...extra }] }];
    expect(isRouteOptions(withLeg({ elevators: [[52.2]] }))).toBe(false);
    expect(isRouteOptions(withLeg({ steps: 'x' }))).toBe(false);
    expect(isRouteOptions(withLeg({ waitS: -1 }))).toBe(false);
    expect(isRouteOptions(withLeg({ waitS: '60' }))).toBe(false);
    expect(isRouteOptions(withLeg({ tripId: 7 }))).toBe(false);
    expect(isRouteOptions([{ ...option, waitS: Number.NaN }])).toBe(false);
    expect(isRouteOptions([{ ...option, waitS: null }])).toBe(true); // null = not given
  });

  it('rejects an answer that is not a list', () => {
    expect(isRouteOptions({ detail: 'error' })).toBe(false);
    expect(isRouteOptions(null)).toBe(false);
  });

  it('accepts optional segments and rejects malformed segment coordinates or kinds', () => {
    const segments = [{ kind: 'push', path: leg.path, lengthM: 12 }];
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, segments }] }])).toBe(true);
    for (const broken of [
      [{ ...segments[0], kind: 'teleport' }],
      [{ ...segments[0], path: [[52.2]] }],
      [{ ...segments[0], lengthM: -1 }],
    ]) {
      expect(isRouteOptions([{ ...option, legs: [{ ...leg, segments: broken }] }])).toBe(false);
    }
  });

  it('accepts a boolean or missing approximatePath and rejects other values', () => {
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, approximatePath: true }] }])).toBe(true);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, approximatePath: false }] }])).toBe(true);
    expect(isRouteOptions([{ ...option, legs: [{ ...leg, approximatePath: 'yes' }] }])).toBe(false);
  });
});

describe('isNearestBuses', () => {
  it('accepts candidates and lines', () => {
    expect(isNearestBuses({ candidates: [{ id: 'a', line: '175' }], lines: ['175'] })).toBe(true);
  });

  it('rejects a missing lines list', () => {
    expect(isNearestBuses({ candidates: [] })).toBe(false);
  });
});

describe('isBusDelay', () => {
  const delay = {
    vehicleId: 'bus-2246',
    line: '517',
    available: true,
    reason: null,
    delaySec: 8,
    prevStop: { id: 'ztm:703302', name: 'Krucza', scheduled: '18:57:00', passedAt: '18:57:08' },
    nextStop: { id: 'ztm:701306', name: 'Centrum', scheduled: '18:59:00', expected: '18:59:08' },
    radiusM: 30,
    updatedAt: 1792249203.8,
  };

  it('accepts an available and an unavailable delay', () => {
    expect(isBusDelay(delay)).toBe(true);
    expect(isBusDelay({ ...delay, available: false, reason: 'no_trip', delaySec: null, prevStop: null, nextStop: null })).toBe(true);
  });

  it('rejects an available delay without seconds', () => {
    expect(isBusDelay({ ...delay, delaySec: null })).toBe(false);
  });

  it('rejects broken fields', () => {
    expect(isBusDelay({ ...delay, delaySec: '8' })).toBe(false);
    expect(isBusDelay({ ...delay, prevStop: { name: 'Krucza' } })).toBe(false);
    expect(isBusDelay({ ...delay, vehicleId: undefined })).toBe(false);
  });

  it('rejects an error answer', () => {
    expect(isBusDelay({ detail: 'unknown vehicle' })).toBe(false);
    expect(isBusDelay(null)).toBe(false);
  });
});

describe('isRouteOptions with the backend null fields', () => {
  // Shape of a real POST /api/routes answer (backend/app/models.py): fields that do not apply to a leg are null.
  const walk = {
    mode: 'walk', from: 'Start', to: 'Plac Konstytucji 03', line: null, durationMin: 4, distanceM: 310,
    path: [[52.2297, 21.0122], [52.2221, 21.0153]], start: [21.0122, 52.2297], end: [21.0153, 52.2221],
    fromId: null, toId: 'ztm:700203', segments: [], approximatePath: false,
    elevators: [], steps: [], waitS: null, tripId: null,
  };
  const bus = {
    mode: 'bus', from: 'Plac Konstytucji 03', to: 'Metro Politechnika 01', line: '16', durationMin: 3, distanceM: 900,
    path: [[52.2221, 21.0153], [52.2190, 21.0110]], start: [21.0153, 52.2221], end: [21.011, 52.219],
    fromId: 'ztm:700203', toId: 'ztm:702301', segments: [], approximatePath: false,
    elevators: null, steps: null, waitS: 109.8, tripId: 'ztm:16:PcM:1',
  };
  const option = {
    id: 'pt-x', title: '16', legs: [walk, bus], departure: '08:00', arrival: '08:09', durationMin: 9, distanceM: 1210,
    walkDistance: 310, bikeDistance: 0, transfers: 0, tags: [], waypoints: [], waitS: 111.8,
  };

  it('accepts null for fields that do not apply to the leg', () => {
    expect(isRouteOptions([option])).toBe(true);
  });

  it('still rejects wrong types', () => {
    expect(isRouteOptions([{ ...option, legs: [{ ...bus, waitS: -1 }] }])).toBe(false);
    expect(isRouteOptions([{ ...option, legs: [{ ...bus, tripId: 7 }] }])).toBe(false);
  });
});
