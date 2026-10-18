import { describe, expect, it } from 'vitest';
import { buildOverlay, stationIds } from './overlay';
import type { Station } from '../api/stations';
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
  walkDistance: 600,
  bikeDistance: 0,
  transfers: 0,
  tags: [],
});
const station = (id: string, lat: number, lon: number, kind = 'bus_post', entrances: [number, number][] = []): Station => ({
  id,
  kind,
  name: id,
  position: [lat, lon],
  entrances,
});

describe('stationIds', () => {
  it('lists the ids of the legs once, without nulls', () => {
    const r = route([leg({ toId: 'ztm:1' }), leg({ fromId: 'ztm:1', toId: 'ztm:2' }), leg({ fromId: 'ztm:2', toId: null })]);
    expect(stationIds(r)).toEqual(['ztm:1', 'ztm:2']);
    expect(stationIds(null)).toEqual([]);
  });
});

describe('buildOverlay', () => {
  it('puts a marker at the position of each stop', () => {
    const r = route([leg({ toId: 'ztm:1' }), leg({ mode: 'bus', fromId: 'ztm:1', path: [[52.2011, 21.0011], [52.21, 21.01]] })]);
    const o = buildOverlay(r, new Map([['ztm:1', station('ztm:1', 52.2011, 21.0011)]]));
    expect(o.markers.map((m) => m.station.position)).toEqual([[52.2011, 21.0011]]);
  });

  it('makes consecutive legs meet at the stop', () => {
    // the walk ends 40 m before the stop; the ride starts 30 m after it
    const r = route([
      leg({ toId: 'ztm:1', path: [[52.2, 21.0], [52.2001, 21.0003]] }),
      leg({ mode: 'bus', fromId: 'ztm:1', path: [[52.2008, 21.0012], [52.21, 21.01]] }),
    ]);
    const stop: [number, number] = [52.2005, 21.0007];
    const o = buildOverlay(r, new Map([['ztm:1', station('ztm:1', ...stop)]]));
    expect(o.paths[0][o.paths[0].length - 1]).toEqual(stop);
    expect(o.paths[1][0]).toEqual(stop);
  });

  it('adds no connector where the leg already ends on the stop', () => {
    const r = route([leg({ toId: 'ztm:1', path: [[52.2, 21.0], [52.201, 21.001]] })]);
    const o = buildOverlay(r, new Map([['ztm:1', station('ztm:1', 52.201, 21.001)]]));
    expect(o.paths[0]).toHaveLength(2);
  });

  it('marks metro platforms underground and shows the entrance where the walk goes down', () => {
    const entrance: [number, number] = [52.2005, 21.0006];
    const metro = station('ztm:7014M:P1', 52.2003, 21.0004, 'metro_platform', [entrance, [52.23, 21.05]]);
    const r = route([
      leg({ toId: 'ztm:7014M:P1', path: [[52.2, 21.0], [52.2004, 21.0005]] }),
      leg({ mode: 'metro', fromId: 'ztm:7014M:P1', path: [[52.2003, 21.0004], [52.22, 21.02]] }),
    ]);
    const o = buildOverlay(r, new Map([[metro.id, metro]]));
    expect(o.markers[0].underground).toBe(true);
    expect(o.entrances).toEqual([entrance]);
  });

  it('ignores ids the server did not know', () => {
    const r = route([leg({ toId: 'ztm:missing' })]);
    const o = buildOverlay(r, new Map());
    expect(o.markers).toEqual([]);
    expect(o.paths[0]).toEqual(r.legs[0].path);
  });
});
