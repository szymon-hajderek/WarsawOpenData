import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoryProvider, useHistory } from './HistoryProvider';
import { fetchSummary, fetchTripRecords } from '../api/history';
import { CITY_SHARING_KEY, logCityEvent } from '../api/cityEvents';
import { EMPTY_SUMMARY } from './types';

vi.mock('../api/history', () => ({ fetchSummary: vi.fn(), fetchTripRecords: vi.fn(), localSummary: () => ({}) }));
vi.mock('../api/cityEvents', async (original) => ({ ...await original<typeof import('../api/cityEvents')>(), logCityEvent: vi.fn() }));
let fix: PositionCallback;
let fail: PositionErrorCallback;
const legs = [{ mode: 'bus' as const, distanceM: 1000 }];
const selection = () => ({
  from: { id: 'current-location', label: 'Private start', position: [52.2, 21] as [number, number] },
  to: { id: 'osm:node:123', label: 'Destination', position: [52.3, 21.1] as [number, number] },
});
function samples() {
  for (const timestamp of [1000, 6000]) fix({ timestamp, coords: { latitude: 52.2, longitude: 21, accuracy: 5 } } as GeolocationPosition);
}

describe('opt-in city journey lifecycle', () => {
  beforeEach(() => {
    localStorage.clear(); vi.clearAllMocks();
    vi.mocked(fetchSummary).mockResolvedValue(EMPTY_SUMMARY);
    vi.mocked(fetchTripRecords).mockResolvedValue([]);
    vi.mocked(logCityEvent).mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: {
      watchPosition: vi.fn((ok, error) => { fix = ok; fail = error; return 1; }), clearWatch: vi.fn(),
    } });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('defaults off and does not inherit the narrower old consent', async () => {
    localStorage.setItem('journey-statistics-enabled', 'true');
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    expect(result.current.shareJourneys).toBe(false);
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(samples);
    await act(() => result.current.tracker.stop());
    expect(logCityEvent).not.toHaveBeenCalled();
  });

  it('snapshots endpoints and links start/finish even for transit-only speed history', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    const chosen = selection();
    act(() => result.current.tracker.start(legs, 'walking', chosen));
    chosen.from.position[0] = 70;
    act(samples);
    await act(() => result.current.tracker.stop());
    const calls = vi.mocked(logCityEvent).mock.calls;
    expect(calls.map((c) => c[0])).toEqual(['journey_started', 'journey_finished']);
    expect(calls[0][1].journey_id).toBe(calls[1][1].journey_id);
    expect(calls[1][1].origin).toEqual({ position: [52.2, 21], station_id: undefined });
    expect(JSON.stringify(calls)).not.toMatch(/Private start|Destination|osm:node|track/);
  });

  it('revoking then re-enabling does not share the remainder of a ride', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(() => { result.current.setShareJourneys(false); result.current.setShareJourneys(true); });
    await act(() => result.current.tracker.stop());
    expect(logCityEvent).toHaveBeenCalledTimes(1);
  });

  it('honors cross-tab revocation', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(() => window.dispatchEvent(new StorageEvent('storage', { key: CITY_SHARING_KEY, newValue: 'false' })));
    await act(() => result.current.tracker.stop());
    expect(result.current.shareJourneys).toBe(false);
    expect(logCityEvent).toHaveBeenCalledTimes(1);
  });

  it('records GPS failure as interruption, never as completed travel', () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(() => fail({} as GeolocationPositionError));
    expect(vi.mocked(logCityEvent).mock.calls.map((c) => c[0])).toEqual(['journey_started', 'journey_interrupted']);
  });

  it('does not retroactively collect a ride started without consent', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(() => result.current.setShareJourneys(true));
    await act(() => result.current.tracker.stop());
    expect(logCityEvent).not.toHaveBeenCalled();
  });
});
