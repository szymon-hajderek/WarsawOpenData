import { afterEach, describe, expect, it, vi } from 'vitest';
import { MIN_QUERY, searchPlaces } from './geocode';

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
    expect(url).toContain('/api/geocode?q=cent');
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
});
