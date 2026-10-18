import { afterEach, describe, expect, it, vi } from 'vitest';
import { BackendOfflineError } from './routes';
import { fetchStreetRoute, fetchStreetTrip, StreetRouteError } from './streetRoute';
import type { Place } from '../types';
import { BIKE_ANSWER, STROLLER_ANSWER } from '../test/streetAnswers';
import { legLines } from '../utils/legStyle';

const from: Place = { id: 'a', label: 'Aleja Solidarności 171', position: [52.2386, 20.9906] };
const to: Place = { id: 'b', label: 'Banderii 4', position: [52.2495, 20.9838] };

/** Answers recorded from the local street router (Al. Solidarności 171 -> Banderii 4), the geometry shortened. */
const GEOMETRY: [number, number][] = [[52.2386, 20.9906], [52.23858, 20.99056], [52.2388, 20.99038], [52.24941, 20.98375], [52.2495, 20.9838]];
const answers = {
  walk: { seconds: 1345.3, walk_m: 1657.3, bike_m: 0, wait_s: 70.4, length_m: 1657.3, snap_m: [1.1, 10.6], geometry: GEOMETRY, elevators: [], steps: [] },
  bike: { seconds: 560.2, walk_m: 122.9, bike_m: 1612.8, wait_s: 81.7, length_m: 1735.7, snap_m: [1.1, 10.6], geometry: GEOMETRY, elevators: [] },
  // the documented shape of an accessible / stroller answer with elevators and steps (data/API.md)
  accessible: { seconds: 1500, walk_m: 1700, bike_m: 0, wait_s: 190, length_m: 1700, snap_m: [1, 2], geometry: GEOMETRY, elevators: [[20.99, 52.24], [20.98, 52.245]], steps: [] },
  stroller: { seconds: 1600, walk_m: 1710, bike_m: 0, wait_s: 130, length_m: 1710, snap_m: [1, 2], geometry: GEOMETRY, elevators: [], steps: [[20.9902, 52.2391]] },
};

const reply = (body: unknown, status = 200) => vi.fn(async () => new Response(JSON.stringify(body), { status }));

describe('fetchStreetRoute', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('asks the router with the mode of the router, not the name of the option', async () => {
    const fetchMock = reply(answers.accessible);
    vi.stubGlobal('fetch', fetchMock);
    await fetchStreetRoute(from, to, 'wheelchair');
    const url = String((fetchMock.mock.calls[0] as unknown[])[0]);
    expect(url).toContain('/api/osm/route?');
    expect(url).toContain('mode=accessible');
    expect(url).toContain('from_lat=52.2386&from_lon=20.9906&to_lat=52.2495&to_lon=20.9838');
  });

  it('walk: one walking leg, distances and times from the answer', async () => {
    vi.stubGlobal('fetch', reply(answers.walk));
    const o = await fetchStreetRoute(from, to, 'walk');
    expect(o.legs).toHaveLength(1);
    expect(o.legs[0]).toMatchObject({ mode: 'walk', durationMin: 22, distanceM: 1657.3, fromId: null, toId: null });
    expect(o).toMatchObject({ walkDistance: 1657.3, bikeDistance: 0, transfers: 0, durationMin: 22, distanceM: 1657.3 });
    expect(o.legs[0].path).toEqual(GEOMETRY);
    expect(o.tags).toEqual([]);
  });

  it('start and end are the first and the last point of the path, as [lon, lat]', async () => {
    vi.stubGlobal('fetch', reply(answers.walk));
    const leg = (await fetchStreetRoute(from, to, 'walk')).legs[0];
    expect(leg.start).toEqual([20.9906, 52.2386]);
    expect(leg.end).toEqual([20.9838, 52.2495]);
  });

  it('own bike: a bike leg with the ridden and the pushed distance', async () => {
    vi.stubGlobal('fetch', reply(answers.bike));
    const o = await fetchStreetRoute(from, to, 'bike');
    expect(o.legs[0].mode).toBe('bike');
    expect(o).toMatchObject({ bikeDistance: 1612.8, walkDistance: 122.9, durationMin: 9, title: 'Własny rower' });
  });

  it('wheelchair: no steps tag and the elevators are counted', async () => {
    vi.stubGlobal('fetch', reply(answers.accessible));
    const o = await fetchStreetRoute(from, to, 'wheelchair');
    expect(o.legs[0].mode).toBe('walk');
    expect(o.tags).toEqual(['bez schodów', 'windy: 2']);
    expect(o.legs[0].elevators).toHaveLength(2);
  });

  it('stroller: keeps the steps with a ramp', async () => {
    vi.stubGlobal('fetch', reply(answers.stroller));
    const o = await fetchStreetRoute(from, to, 'stroller');
    expect(o.title).toBe('Wózek dziecięcy');
    expect(o.legs[0].steps).toEqual([[20.9902, 52.2391]]);
    expect(o.tags).toEqual(['bez schodów']);
  });

  it.each([
    [422, 'Punkt poza zasięgiem mapy'],
    [404, 'Brak trasy'],
    [503, 'Serwer tras nie działa'],
    [400, 'Ten tryb nie jest jeszcze dostępny na serwerze'],
  ])('answer %i is said in Polish', async (status, text) => {
    vi.stubGlobal('fetch', reply({ detail: 'x' }, status));
    const err = await fetchStreetRoute(from, to, 'walk').catch((e) => e);
    expect(err).toBeInstanceOf(StreetRouteError);
    expect(err.message).toBe(text);
  });

  it.each(['wheelchair', 'stroller'] as const)('%s never falls back to a made-up or straight route', async (mode) => {
    vi.stubGlobal('fetch', reply({ detail: 'down' }, 503));
    await expect(fetchStreetRoute(from, to, mode)).rejects.toThrow('Serwer tras nie działa');
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    await expect(fetchStreetRoute(from, to, mode)).rejects.toBeInstanceOf(BackendOfflineError);
  });

  it('an answer without a geometry is not trusted', async () => {
    vi.stubGlobal('fetch', reply({ seconds: 10, walk_m: 1, bike_m: 0, length_m: 1 }));
    await expect(fetchStreetRoute(from, to, 'walk')).rejects.toThrow('Serwer tras nie działa');
  });
});

describe('fetchStreetRoute: segments', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const sum = (xs: { lengthM: number }[]) => xs.reduce((s, x) => s + x.lengthM, 0);

  it('bike: segments come as [lat, lon] with lengthM', async () => {
    vi.stubGlobal('fetch', reply(BIKE_ANSWER));
    const segs = (await fetchStreetRoute(from, to, 'bike')).legs[0].segments!;
    expect(segs.map((s) => s.kind)).toEqual(['push', 'ride', 'push', 'ride', 'push']);
    expect(segs[0]).toEqual({ kind: 'push', lengthM: 4.0, path: [[52.2297, 21.0122], [52.22969, 21.01226]] });
  });

  it('bike: ridden metres sum to bike_m, the rest to walk_m', async () => {
    vi.stubGlobal('fetch', reply(BIKE_ANSWER));
    const segs = (await fetchStreetRoute(from, to, 'bike')).legs[0].segments!;
    expect(Math.abs(sum(segs.filter((s) => s.kind === 'ride')) - BIKE_ANSWER.bike_m)).toBeLessThanOrEqual(1);
    expect(Math.abs(sum(segs.filter((s) => s.kind !== 'ride')) - BIKE_ANSWER.walk_m)).toBeLessThanOrEqual(1);
  });

  it.each([
    ['bike', BIKE_ANSWER],
    ['stroller', STROLLER_ANSWER],
  ] as const)('%s: consecutive segments touch and cover the whole path', async (mode, answer) => {
    vi.stubGlobal('fetch', reply(answer));
    const leg = (await fetchStreetRoute(from, to, mode)).legs[0];
    const segs = leg.segments!;
    for (let i = 1; i < segs.length; i++) expect(segs[i].path[0]).toEqual(segs[i - 1].path[segs[i - 1].path.length - 1]);
    expect(segs[0].path[0]).toEqual(leg.path[0]);
    expect(segs[segs.length - 1].path.slice(-1)).toEqual(leg.path.slice(-1));
  });

  it('stroller: walk, steps and elevator segments; walked metres sum to walk_m', async () => {
    vi.stubGlobal('fetch', reply(STROLLER_ANSWER));
    const o = await fetchStreetRoute(from, to, 'stroller');
    const segs = o.legs[0].segments!;
    expect(segs.map((s) => s.kind)).toEqual(['walk', 'steps', 'walk', 'elevator', 'walk']);
    expect(Math.abs(sum(segs) - STROLLER_ANSWER.walk_m)).toBeLessThanOrEqual(1);
    expect(legLines(o.legs[0]).map((l) => l.style)).toEqual(['dotted', 'access', 'dotted', 'access', 'dotted']);
  });

  it('a leg without segments (older server) is still one line', async () => {
    vi.stubGlobal('fetch', reply(answers.bike));
    const leg = (await fetchStreetRoute(from, to, 'bike')).legs[0];
    expect(leg.segments).toBeUndefined();
    expect(legLines(leg)).toEqual([{ path: GEOMETRY, style: 'solid' }]);
  });

  it('a segment with a bad kind or path is not trusted', async () => {
    const bad = (segment: object) => ({ ...BIKE_ANSWER, legs: [{ ...BIKE_ANSWER.legs[0], segments: [segment] }] });
    vi.stubGlobal('fetch', reply(bad({ kind: 'fly', length_m: 1, path: [[21, 52]] })));
    await expect(fetchStreetRoute(from, to, 'bike')).rejects.toThrow('Serwer tras nie działa');
    vi.stubGlobal('fetch', reply(bad({ kind: 'ride', length_m: 1, path: [[21]] })));
    await expect(fetchStreetRoute(from, to, 'bike')).rejects.toThrow('Serwer tras nie działa');
  });
});

describe('fetchStreetTrip', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('chains one path per pair of points through the stops', async () => {
    vi.stubGlobal('fetch', reply(answers.walk));
    const stop: Place = { id: 's', label: 'Przystanek', position: [52.243, 20.987] };
    const options = await fetchStreetTrip({ from, to, via: [stop] }, 'walk');
    expect(options).toHaveLength(1);
    expect(options[0].legs).toHaveLength(2);
    expect(options[0].legs[0].stop).toBe(1);
    expect(options[0].waypoints?.map((p) => p.id)).toEqual(['a', 's', 'b']);
    expect(options[0].walkDistance).toBeCloseTo(2 * 1657.3, 1);
  });
});
