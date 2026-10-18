import { describe, expect, it } from 'vitest';
import { isNearestBuses, isRouteOptions } from './validate';

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
    expect(isRouteOptions([{ ...option, waitS: null }])).toBe(false);
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
