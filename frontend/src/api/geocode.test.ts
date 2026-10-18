import { afterEach, describe, expect, it, vi } from 'vitest';
import { MIN_QUERY, mergePlaces, searchPlaces } from './geocode';
import type { Place } from '../types';

describe('searchPlaces', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends the position of the user so close stops come first', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify([{ id: 'stop-1', label: 'Centrum', position: [52.2, 21.0] }])));
    vi.stubGlobal('fetch', fetchMock);
    const places = await searchPlaces('cent', undefined, [52.23, 21.01]);
    expect(places[0].label).toBe('Centrum');
    const url = String((fetchMock.mock.calls[0] as unknown[])[0]);
    expect(url).toContain('/api/geocode?q=cent&source=local');
    expect(url).toContain('lat=52.23&lon=21.01');
  });

  it('starts at 2 characters with the backend', () => {
    expect(MIN_QUERY).toBe(2);
  });

  it('answers from the bundled list when the backend is down, without asking Nominatim for a short text', async () => {
    const fetchMock = vi.fn(async () => new Response('x', { status: 500 }));
    vi.stubGlobal('fetch', fetchMock);
    const places = await searchPlaces('marszalk');
    expect(places.length).toBeGreaterThan(0);
    expect(places[0].label).toContain('Marszałkowska');
    expect(fetchMock).toHaveBeenCalledTimes(2); // the backend, then Nominatim for addresses (8 characters)
    fetchMock.mockClear();
    expect((await searchPlaces('ma')).length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the backend: 2 characters never go to Nominatim
  });

  it('keeps the stops when Nominatim fails too', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))));
    const places = await searchPlaces('politechn');
    expect(places.some((p) => p.label.includes('Politechnika'))).toBe(true);
  });

  it('hands our own places over at once and merges Nominatim in later', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const body = url.includes('source=local')
        ? [{ id: 'stop-1', label: 'Pl. Zbawiciela', position: [52.22, 21.02] }]
        : [
            { id: 'osm:way:1', label: 'Plac Zbawiciela', position: [52.22, 21.02] },
            { id: 'osm:way:2', label: 'pl. zbawiciela', position: [52.22, 21.02] },
          ];
      return new Response(JSON.stringify(body));
    });
    vi.stubGlobal('fetch', fetchMock);
    const onLocal = vi.fn();
    const places = await searchPlaces('zbawiciela', undefined, undefined, onLocal);
    expect(onLocal).toHaveBeenCalledWith([expect.objectContaining({ id: 'stop-1' })]);
    expect(String((fetchMock.mock.calls[1] as unknown[])[0])).toContain('source=nominatim');
    expect(places.map((p) => p.id)).toEqual(['stop-1', 'osm:way:1']); // the same name is not repeated
  });

  it('does not ask Nominatim when the query changed in the meantime', async () => {
    const fetchMock = vi.fn(async () => new Response('[]'));
    vi.stubGlobal('fetch', fetchMock);
    const ac = new AbortController();
    const search = searchPlaces('arkadia', ac.signal, undefined, () => ac.abort());
    await expect(search).rejects.toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the local part
  });

  it('keeps our places when Nominatim fails on the backend', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes('source=local')
        ? new Response(JSON.stringify([{ id: 'place-1', label: 'Westfield Arkadia', position: [52.25, 20.98] }]))
        : new Response('{"detail": "Geocoding service failed"}', { status: 502 }),
    );
    vi.stubGlobal('fetch', fetchMock);
    expect((await searchPlaces('arkadia')).map((p) => p.id)).toEqual(['place-1']);
  });
});

describe('mergePlaces', () => {
  const stop: Place = { id: 'stop-1', label: 'Marszałkowska', position: [52.2, 21.0] };
  const address: Place = { id: 'osm:way:1', label: 'Marszałkowska 1', position: [52.2, 21.0] };

  it('puts Nominatim first for a street address', () => {
    expect(mergePlaces('Marszałkowska 1', [stop], [address]).map((p) => p.id)).toEqual(['osm:way:1', 'stop-1']);
  });

  it('puts our places first otherwise', () => {
    expect(mergePlaces('marszałkowska', [stop], [address]).map((p) => p.id)).toEqual(['stop-1', 'osm:way:1']);
  });
});
