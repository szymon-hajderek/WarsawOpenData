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

  it('does not ask Nominatim directly for a short text when the backend is down', async () => {
    const fetchMock = vi.fn(async () => new Response('x', { status: 500 }));
    vi.stubGlobal('fetch', fetchMock);
    expect(await searchPlaces('ce')).toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the backend, no Nominatim
  });
});
