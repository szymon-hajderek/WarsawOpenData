import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoryProvider, useHistory } from './HistoryProvider';
import { fetchSummary, fetchTripRecords } from '../api/history';
import { logJourney, type JourneySelection } from '../api/journeys';
import { EMPTY_SUMMARY } from './types';

vi.mock('../api/history', () => ({ fetchSummary: vi.fn(), fetchTripRecords: vi.fn(), localSummary: () => ({}) }));
vi.mock('../api/journeys', async (original) => ({ ...await original<typeof import('../api/journeys')>(), logJourney: vi.fn() }));

let fix: PositionCallback;
let fail: PositionErrorCallback;
const legs = [{ mode: 'bus' as const, distanceM: 1000 }];
const selection = (): JourneySelection => ({
  from: { id: 'current-location', label: 'Private start', isCurrentLocation: true, position: [52.2, 21] },
  to: { id: 'osm:node:123', label: 'Destination', position: [52.3, 21.1] }, mock: false,
});

function samples() {
  for (const timestamp of [1000, 6000]) {
    fix({ timestamp, coords: { latitude: 52.2, longitude: 21, accuracy: 5 } } as GeolocationPosition);
  }
}

describe('completed journey sharing', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    vi.mocked(fetchSummary).mockResolvedValue(EMPTY_SUMMARY);
    vi.mocked(fetchTripRecords).mockResolvedValue([]);
    vi.mocked(logJourney).mockResolvedValue(true);
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: {
      watchPosition: vi.fn((ok, error) => { fix = ok; fail = error; return 1; }), clearWatch: vi.fn(),
    } });
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it('defaults to off and never submits a journey without opt-in', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    expect(result.current.shareJourneys).toBe(false);
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(samples);
    await act(() => result.current.tracker.stop());
    expect(logJourney).not.toHaveBeenCalled();
  });

  it('captures selected endpoints at start and counts transit even without speed records', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    const chosen = selection();
    act(() => result.current.tracker.start(legs, 'walking', chosen));
    chosen.from.position[0] = 70;
    chosen.to.id = 'osm:node:999';
    act(samples);
    expect(logJourney).not.toHaveBeenCalled();
    await act(() => result.current.tracker.stop());
    const payload = vi.mocked(logJourney).mock.calls[0][0];
    expect(payload.from.position).toEqual([52.2, 21]);
    expect(payload.to.id).toBe('osm:node:123');
    expect(JSON.stringify(payload)).not.toMatch(/Private start|Destination|track|legs/);
    expect(payload.token).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('revoking and re-enabling consent does not retroactively share a recording', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(samples);
    act(() => { result.current.setShareJourneys(false); result.current.setShareJourneys(true); });
    await act(() => result.current.tracker.stop());
    expect(logJourney).not.toHaveBeenCalled();
  });

  it('honors consent revocation from another tab', async () => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(samples);
    act(() => window.dispatchEvent(new StorageEvent('storage', { key: 'journey-statistics-enabled', newValue: 'false' })));
    await act(() => result.current.tracker.stop());
    expect(result.current.shareJourneys).toBe(false);
    expect(logJourney).not.toHaveBeenCalled();
  });

  it.each(['mock', 'no GPS', 'interrupted', 'enabled mid-ride'])('does not share %s recordings', async (kind) => {
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    if (kind !== 'enabled mid-ride') act(() => result.current.setShareJourneys(true));
    act(() => result.current.tracker.start(legs, 'walking', { ...selection(), mock: kind === 'mock' }));
    if (kind !== 'no GPS') act(samples);
    if (kind === 'enabled mid-ride') act(() => result.current.setShareJourneys(true));
    if (kind === 'interrupted') {
      act(() => fail({} as GeolocationPositionError));
      await act(() => result.current.tracker.retry());
    } else await act(() => result.current.tracker.stop());
    expect(logJourney).not.toHaveBeenCalled();
  });

  it('does not block speed-history saving when statistics are unavailable', async () => {
    vi.mocked(logJourney).mockResolvedValue(false);
    const { result } = renderHook(useHistory, { wrapper: HistoryProvider });
    act(() => result.current.setShareJourneys(true));
    act(() => result.current.tracker.start(legs, 'walking', selection()));
    act(samples);
    await act(() => result.current.tracker.stop());
    expect(fetchTripRecords).toHaveBeenCalledOnce();
    expect(result.current.tracker.status).toBe('done');
  });
});
