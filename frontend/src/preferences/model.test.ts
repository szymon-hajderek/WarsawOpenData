import { describe, expect, it } from 'vitest';
import { DEFAULT_PREFERENCES, routeKcal } from './model';
import type { RouteLeg } from '../types';

const leg = (mode: RouteLeg['mode'], distanceM: number, durationMin: number): RouteLeg => ({
  mode,
  from: 'a',
  to: 'b',
  durationMin,
  distanceM,
  path: [[52.2, 21.0]],
});

describe('routeKcal', () => {
  it('counts a Veturilo leg like an own bike', () => {
    const own = routeKcal({ legs: [leg('bike', 5000, 15)] }, DEFAULT_PREFERENCES);
    const rented = routeKcal({ legs: [leg('veturilo', 5000, 15)] }, DEFAULT_PREFERENCES);
    expect(rented).toBe(own);
    expect(rented).toBeGreaterThan(0);
  });

  it('uses the speed of the leg itself', () => {
    const fast = routeKcal({ legs: [leg('veturilo', 5000, 15)] }, DEFAULT_PREFERENCES);
    const slow = routeKcal({ legs: [leg('veturilo', 5000, 30)] }, DEFAULT_PREFERENCES);
    expect(fast).not.toBe(slow);
  });

  it('treats public transport as rest', () => {
    expect(routeKcal({ legs: [leg('bus', 8000, 20)] }, DEFAULT_PREFERENCES)).toBe(0);
  });
});
