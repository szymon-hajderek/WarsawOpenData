import { afterEach, describe, expect, it, vi } from 'vitest';
import { BackendOfflineError, fetchRouteOptions } from './routes';
import { detectVehicle } from './vehicle';

const place = (id: string, lat: number) => ({ id, label: id, position: [lat, 21.0] as [number, number] });
const query = { from: place('a', 52.2), to: place('b', 52.25), profile: 'standard' as const };

describe('backend not connected', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('routes: a network error is reported, not replaced by made-up routes', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    await expect(fetchRouteOptions(query)).rejects.toBeInstanceOf(BackendOfflineError);
  });

  it('routes: a server error or an unusable answer counts as not connected', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('boom', { status: 503 })));
    await expect(fetchRouteOptions(query)).rejects.toBeInstanceOf(BackendOfflineError);
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'x' }))));
    await expect(fetchRouteOptions(query)).rejects.toBeInstanceOf(BackendOfflineError);
  });

  it('routes: a refused query (4xx) is a different error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 422 })));
    const err = await fetchRouteOptions(query).catch((e) => e);
    expect(err).toBeInstanceOf(Error);
    expect(err).not.toBeInstanceOf(BackendOfflineError);
  });

  it('routes: a good answer is returned as real data', async () => {
    const legs = [{ mode: 'walk', durationMin: 5, distanceM: 300, path: [[52.2, 21.0], [52.21, 21.0]] }];
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([{ id: 'x', legs, tags: [] }]))));
    const result = await fetchRouteOptions(query);
    expect(result.mock).toBe(false);
    expect(result.options[0].id).toBe('x');
  });

  it('vehicle: nothing is detected and the result says offline', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))));
    const result = await detectVehicle([], [52.2, 21.0]);
    expect(result).toMatchObject({ candidates: [], mock: false, offline: true });
  });
});
