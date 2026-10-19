import { describe, expect, it } from 'vitest';
import { routeGeoJson } from './route3d';
import type { RouteLeg, RouteOption } from '../types';

const leg = (over: Partial<RouteLeg>): RouteLeg => ({
  mode: 'walk',
  from: 'a',
  to: 'b',
  durationMin: 5,
  distanceM: 300,
  path: [[52.2, 21.0], [52.201, 21.001]],
  ...over,
});
const route = (legs: RouteLeg[]): RouteOption => ({
  id: 'r',
  title: 't',
  legs,
  departure: '10:00',
  arrival: '10:30',
  durationMin: 30,
  distanceM: 3000,
  walkDistance: 300,
  bikeDistance: 0,
  transfers: 0,
  tags: [],
});

describe('routeGeoJson', () => {
  it('makes one line per leg, in [lon, lat] order', () => {
    const fc = routeGeoJson(route([leg({}), leg({ mode: 'bus', line: '175', path: [[52.21, 21.01], [52.22, 21.02]] })]), 'light');
    expect(fc.features).toHaveLength(2);
    expect(fc.features[0].geometry.coordinates[0]).toEqual([21.0, 52.2]);
    expect(fc.features[1].geometry.coordinates[1]).toEqual([21.02, 52.22]);
  });

  it('walking is dotted without a casing, a ride is solid with one', () => {
    const [walk, ride] = routeGeoJson(route([leg({}), leg({ mode: 'tram', path: [[52.21, 21.01], [52.22, 21.02]] })]), 'dark').features;
    expect(walk.properties).toMatchObject({ style: 'dotted', casing: false });
    expect(ride.properties).toMatchObject({ style: 'solid', casing: true });
    expect(walk.properties.color).not.toBe(ride.properties.color);
  });

  it('draws the parts of a bike leg by their kind: ridden solid, pushed dashed', () => {
    const bike = leg({
      mode: 'bike',
      path: [[52.2, 21.0], [52.21, 21.01]],
      segments: [
        { kind: 'ride', lengthM: 100, path: [[52.2, 21.0], [52.205, 21.005]] },
        { kind: 'push', lengthM: 20, path: [[52.205, 21.005], [52.21, 21.01]] },
      ],
    });
    const styles = routeGeoJson(route([bike]), 'light').features.map((f) => f.properties.style);
    expect(styles).toEqual(['solid', 'dashed']);
  });

  it('skips a line that has fewer than two points', () => {
    expect(routeGeoJson(route([leg({ path: [[52.2, 21.0]] })]), 'light').features).toHaveLength(0);
  });
});
