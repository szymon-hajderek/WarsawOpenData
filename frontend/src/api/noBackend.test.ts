import { afterEach, describe, expect, it, vi } from 'vitest';

// The backend is switched off on purpose (`VITE_API_URL=""`).
vi.mock('../config', () => ({ API_URL: '', apiUrl: (path: string) => path }));

import { BackendOfflineError, fetchRouteOptions } from './routes';
import { detectVehicle } from './vehicle';

const place = (id: string, lat: number) => ({ id, label: id, position: [lat, 21.0] as [number, number] });

describe('backend switched off (empty API_URL)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('routes: the offline error, no example data and no request', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    await expect(fetchRouteOptions({ from: place('a', 52.2), to: place('b', 52.25), profile: 'standard' })).rejects.toBeInstanceOf(
      BackendOfflineError,
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('vehicle: offline, no candidates', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const result = await detectVehicle([], [52.2, 21.0]);
    expect(result).toEqual({ candidates: [], lines: [], offline: true });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
