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

  it('rejects an answer that is not a list', () => {
    expect(isRouteOptions({ detail: 'error' })).toBe(false);
    expect(isRouteOptions(null)).toBe(false);
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
