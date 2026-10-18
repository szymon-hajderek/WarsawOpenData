import { afterEach, describe, expect, it, vi } from 'vitest';
import { BackendOfflineError } from './routes';
import { fetchStreetRoute, fetchStreetTrip, StreetRouteError } from './streetRoute';
import type { Place } from '../types';

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

  it('keeps access costs and endpoints while supplying graph geometry for the map', async () => {
    const network = GEOMETRY.slice(1, -1);
    vi.stubGlobal('fetch', reply({ ...answers.walk, network_geometry: network }));
    const o = await fetchStreetRoute(from, to, 'walk');
    expect(o.legs[0].networkPath).toEqual(network);
    expect(o.legs[0].path).toEqual(GEOMETRY);
    expect(o.legs[0].start).toEqual([20.9906, 52.2386]);
    expect(o).toMatchObject({ distanceM: 1657.3, durationMin: 22 });
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
