import { describe, expect, it } from 'vitest';
import { nextStepText, OFF_ROUTE_M, routeProgress } from './progress';
import { BUS_PATH, ROUTE_119, seeded, WALK_START, withNoise } from '../test/tripFixtures';
import type { RouteLeg } from '../types';

describe('routeProgress on a recorded bus track', () => {
  it('follows the user along the route (walk, then the recorded bus track with GPS noise)', () => {
    const rnd = seeded(7);
    let along = 0;
    // walking to the stop
    const walk = routeProgress(ROUTE_119, withNoise(WALK_START, 10, rnd), along);
    expect(walk.legIndex).toBe(0);
    expect(walk.nextStep).toBe('Idź do: Grochowska 01');
    along = walk.alongM;

    // on the bus: every recorded position of bus-1002 with up to 20 m of GPS error
    const seen: number[] = [];
    for (const p of BUS_PATH.slice(1, -1)) {
      const r = routeProgress(ROUTE_119, withNoise(p, 20, rnd), along);
      expect(r.offRoute).toBe(false);
      expect(r.alongM).toBeGreaterThanOrEqual(along); // forward only
      along = r.alongM;
      seen.push(r.legIndex);
    }
    expect(seen.every((i) => i === 1)).toBe(true);
    expect(routeProgress(ROUTE_119, BUS_PATH[6], along).nextStep).toBe('Wysiadasz na: Rondo Wiatraczna 02');
  });

  it('never goes back: a position near the start after riding keeps the progress', () => {
    const mid = routeProgress(ROUTE_119, BUS_PATH[8], 0);
    const back = routeProgress(ROUTE_119, BUS_PATH[1], mid.alongM);
    expect(back.alongM).toBe(mid.alongM);
    expect(back.legIndex).toBe(1);
  });

  it('says "Zboczyłeś z trasy" more than 150 m away', () => {
    const p = BUS_PATH[6];
    const near = routeProgress(ROUTE_119, [p[0] + 100 / 111_320, p[1]], 0);
    expect(near.offRoute).toBe(false);
    const far = routeProgress(ROUTE_119, [p[0] + 400 / 111_320, p[1]], 0);
    expect(far.offRoute).toBe(true);
    expect(far.offsetM).toBeGreaterThan(OFF_ROUTE_M);
    expect(far.alongM).toBe(0); // off the route the progress does not move
  });
});

describe('nextStepText', () => {
  const leg = (mode: RouteLeg['mode'], from: string, to: string, line?: string): RouteLeg => ({
    mode,
    from,
    to,
    line,
    durationMin: 1,
    distanceM: 100,
    path: [],
  });
  const legs = [leg('walk', 'Start', 'Centrum 01'), leg('tram', 'Centrum 01', 'Plac Zawiszy 03', '9'), leg('walk', 'Plac Zawiszy 03', 'Plac Zawiszy 05'), leg('bus', 'Plac Zawiszy 05', 'Okęcie', '175'), leg('walk', 'Okęcie', 'Cel')];

  it('names the stop to get off, the transfer and where to walk', () => {
    expect(nextStepText(legs, 0)).toBe('Idź do: Centrum 01');
    expect(nextStepText(legs, 1)).toBe('Wysiadasz na: Plac Zawiszy 03');
    expect(nextStepText(legs, 2)).toBe('Przesiadka: 175 z Plac Zawiszy 05');
    expect(nextStepText(legs, 4)).toBe('Idź do: Cel');
  });
});
