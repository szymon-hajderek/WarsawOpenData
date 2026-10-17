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
