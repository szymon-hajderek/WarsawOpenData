import { afterEach, describe, expect, it, vi } from 'vitest';
import { BackendOfflineError } from './routes';
import { fetchStreetRoute, fetchStreetTrip, StreetRouteError } from './streetRoute';
import type { Place } from '../types';
import { BIKE_ANSWER, STROLLER_ANSWER, WALK_ANSWER } from '../test/streetAnswers';
import { legLines } from '../utils/legStyle';

const from: Place = { id: 'a', label: 'Centrum', position: [52.2297, 21.0122] };
const to: Place = { id: 'b', label: 'Ochota', position: [52.2196, 20.9652] };

const reply = (body: unknown, status = 200) => vi.fn(async () => new Response(JSON.stringify(body), { status }));
const sentBody = (fetchMock: ReturnType<typeof reply>) => {
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
  return { url, init, body: JSON.parse(String(init.body)) };
};

describe('fetchStreetRoute', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts to /api/routes with the travel of the router, not the name of the option', async () => {
    const fetchMock = reply(STROLLER_ANSWER);
    vi.stubGlobal('fetch', fetchMock);
    await fetchStreetRoute(from, to, 'wheelchair');
    const { url, init, body } = sentBody(fetchMock);
    expect(url).toMatch(/\/api\/routes$/);
    expect(init.method).toBe('POST');
    expect(body).toEqual({ from, to, travel: 'accessible' });
  });

  it.each([
    ['walk', 'walk'],
    ['stroller', 'stroller'],
    ['bike', 'bike'],
  ] as const)('%s is sent as travel %s', async (mode, travel) => {
    const fetchMock = reply(WALK_ANSWER);
    vi.stubGlobal('fetch', fetchMock);
    await fetchStreetRoute(from, to, mode);
    expect(sentBody(fetchMock).body.travel).toBe(travel);
  });

  it('returns the one option of the answer as it is', async () => {
    vi.stubGlobal('fetch', reply(WALK_ANSWER));
    const o = await fetchStreetRoute(from, to, 'walk');
    expect(o).toEqual(WALK_ANSWER[0]);
    expect(o.legs).toHaveLength(1);
    expect(o.waitS).toBe(180.2);
  });

  it('stroller: elevators are [lat, lon] and lie on the path', async () => {
    vi.stubGlobal('fetch', reply(STROLLER_ANSWER));
    const leg = (await fetchStreetRoute(from, to, 'stroller')).legs[0];
    expect(leg.elevators).toHaveLength(2);
    for (const p of leg.elevators!) expect(leg.path).toContainEqual(p);
    expect(leg.elevators![0][0]).toBeCloseTo(52.23, 1);
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

  it('an empty answer is "no route"', async () => {
    vi.stubGlobal('fetch', reply([]));
    await expect(fetchStreetRoute(from, to, 'walk')).rejects.toThrow('Brak trasy');
  });

  it.each(['wheelchair', 'stroller'] as const)('%s never falls back to a made-up or straight route', async (mode) => {
    vi.stubGlobal('fetch', reply({ detail: 'down' }, 503));
    await expect(fetchStreetRoute(from, to, mode)).rejects.toThrow('Serwer tras nie działa');
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    await expect(fetchStreetRoute(from, to, mode)).rejects.toBeInstanceOf(BackendOfflineError);
  });

  it('an answer of the wrong shape is not trusted', async () => {
    vi.stubGlobal('fetch', reply({ seconds: 10, walk_m: 1, bike_m: 0, length_m: 1 }));
    await expect(fetchStreetRoute(from, to, 'walk')).rejects.toThrow('Serwer tras nie działa');
    const badLift = [{ ...WALK_ANSWER[0], legs: [{ ...WALK_ANSWER[0].legs[0], elevators: [[52.2]] }] }];
    vi.stubGlobal('fetch', reply(badLift));
    await expect(fetchStreetRoute(from, to, 'walk')).rejects.toThrow('Serwer tras nie działa');
  });
});

describe('fetchStreetRoute: segments', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const sum = (xs: { lengthM: number }[]) => xs.reduce((s, x) => s + x.lengthM, 0);

  it('bike: ridden metres sum to bikeDistance, the rest to walkDistance', async () => {
    vi.stubGlobal('fetch', reply(BIKE_ANSWER));
    const o = await fetchStreetRoute(from, to, 'bike');
    const segs = o.legs[0].segments!;
    expect(segs.map((s) => s.kind)).toEqual(['push', 'ride', 'push', 'ride', 'push']);
    expect(Math.abs(sum(segs.filter((s) => s.kind === 'ride')) - o.bikeDistance)).toBeLessThanOrEqual(1);
    expect(Math.abs(sum(segs.filter((s) => s.kind !== 'ride')) - o.walkDistance)).toBeLessThanOrEqual(1);
  });

  it('stroller: walk and elevator segments drawn in their own style', async () => {
    vi.stubGlobal('fetch', reply(STROLLER_ANSWER));
    const leg = (await fetchStreetRoute(from, to, 'stroller')).legs[0];
    expect(leg.segments!.map((s) => s.kind)).toEqual(['walk', 'elevator', 'walk', 'elevator', 'walk']);
    expect(legLines(leg).map((l) => l.style)).toEqual(['dotted', 'access', 'dotted', 'access', 'dotted']);
  });

  it('a segment with a bad kind is not trusted', async () => {
    const leg = BIKE_ANSWER[0].legs[0];
    const bad = [{ ...BIKE_ANSWER[0], legs: [{ ...leg, segments: [{ kind: 'fly', lengthM: 1, path: [[52, 21]] }] }] }];
    vi.stubGlobal('fetch', reply(bad));
    await expect(fetchStreetRoute(from, to, 'bike')).rejects.toThrow('Serwer tras nie działa');
  });
});

describe('fetchStreetTrip', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends the stops and their order in one request', async () => {
    const fetchMock = reply(WALK_ANSWER);
    vi.stubGlobal('fetch', fetchMock);
    const stop: Place = { id: 's', label: 'Przystanek', position: [52.225, 20.99] };
    const options = await fetchStreetTrip({ from, to, via: [stop], order: 'optimal' }, 'walk');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentBody(fetchMock).body).toEqual({ from, to, travel: 'walk', via: [stop], order: 'optimal' });
    expect(options).toHaveLength(1);
  });

  it('sends the pace from the preferences (the bike speed only for the own bike)', async () => {
    const cases: [Parameters<typeof fetchStreetTrip>[0]['pace'], 'bike' | 'walk', object][] = [
      [{ walkKmh: 4.8, bikeKmh: 13 }, 'bike', { walkKmh: 4.8, bikeKmh: 13 }],
      [{ walkKmh: 4.8, bikeKmh: 13 }, 'walk', { walkKmh: 4.8 }],
      [{ bikeKmh: 0 }, 'bike', {}],
    ];
    for (const [pace, mode, extra] of cases) {
      const fetchMock = reply(WALK_ANSWER);
      vi.stubGlobal('fetch', fetchMock);
      await fetchStreetTrip({ from, to, pace }, mode);
      expect(sentBody(fetchMock).body).toEqual({ from, to, travel: mode, ...extra });
    }
  });
});
