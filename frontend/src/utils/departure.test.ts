import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { departureLabel, departureSummary, departureWhen, isPastDeparture } from './departure';
import { fetchRouteOptions } from '../api/routes';
import { fetchStreetTrip } from '../api/streetRoute';
import { useRouteSearch } from '../hooks/useRouteSearch';
import type { Place } from '../types';

const now = new Date(2026, 9, 18, 12, 0); // Sunday 18.10.2026, 12:00 local

describe('departure labels', () => {
  it('says now, today, tomorrow or the date', () => {
    expect(departureLabel(null, now)).toBe('Wyjazd: Teraz');
    expect(departureLabel('2026-10-18T14:30', now)).toBe('Wyjazd: dziś 14:30');
    expect(departureLabel('2026-10-19T08:00', now)).toBe('Wyjazd: jutro 08:00');
    expect(departureLabel('2026-10-20T08:05', now)).toBe('Wyjazd: 20.10 08:05');
    expect(departureLabel('2026-11-01T00:00', new Date(2026, 9, 31, 22, 0))).toBe('Wyjazd: jutro 00:00');
  });

  it('route list header: only when not now', () => {
    expect(departureSummary(null, now)).toBeNull();
    expect(departureSummary('2026-10-18T14:30', now)).toBe('Wyjazd 14:30');
    expect(departureSummary('2026-10-19T08:00', now)).toBe('Wyjazd jutro 08:00');
    expect(departureSummary('2026-10-20T08:00', now)).toBe('Wyjazd 20.10 08:00');
  });

  it('a time earlier today is past; now and later are not', () => {
    expect(isPastDeparture('2026-10-18T11:59', now)).toBe(true);
    expect(isPastDeparture('2026-10-17T23:00', now)).toBe(true);
    expect(isPastDeparture('2026-10-18T12:00', now)).toBe(false);
    expect(isPastDeparture('2026-10-19T06:00', now)).toBe(false);
    expect(isPastDeparture(null, now)).toBe(false);
  });

  it('now sends no when', () => {
    expect(departureWhen(null)).toBeUndefined();
    expect(departureWhen('2026-10-18T14:30')).toBe('2026-10-18T14:30');
  });
});

const place = (id: string, lat: number): Place => ({ id, label: id, position: [lat, 21.0] });
const from = place('a', 52.2);
const to = place('b', 52.25);
const ANSWER = [{ id: 'x', legs: [{ mode: 'walk', durationMin: 5, distanceM: 300, path: [[52.2, 21.0], [52.21, 21.0]] }], tags: [] }];
const okFetch = () => vi.fn(async () => new Response(JSON.stringify(ANSWER)));
const bodies = (f: ReturnType<typeof okFetch>) =>
  f.mock.calls.map((c) => JSON.parse(String((c as unknown as [string, RequestInit])[1].body)));

describe('departure in the request', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('transit: when only for a chosen time, also with stops', async () => {
    const f = okFetch();
    vi.stubGlobal('fetch', f);
    await fetchRouteOptions({ from, to, profile: 'standard' });
    await fetchRouteOptions({ from, to, profile: 'standard', when: '2026-10-19T08:00' });
    await fetchRouteOptions({ from, to, profile: 'standard', via: [place('c', 52.22)], when: '2026-10-19T08:00' });
    const [plain, timed, multi] = bodies(f);
    expect(plain).not.toHaveProperty('when');
    expect(timed.when).toBe('2026-10-19T08:00');
    expect(multi.when).toBe('2026-10-19T08:00');
    expect(multi.via).toHaveLength(1);
  });

  it('street trip: when only for a chosen time', async () => {
    const f = okFetch();
    vi.stubGlobal('fetch', f);
    await fetchStreetTrip({ from, to }, 'walk');
    await fetchStreetTrip({ from, to, when: '2026-10-18T14:30' }, 'walk');
    const [plain, timed] = bodies(f);
    expect(plain).not.toHaveProperty('when');
    expect(timed).toMatchObject({ travel: 'walk', when: '2026-10-18T14:30' });
  });

  it('changing the departure runs a new search', async () => {
    const f = okFetch();
    vi.stubGlobal('fetch', f);
    const via: Place[] = [];
    const { rerender, result } = renderHook((when?: string) => useRouteSearch({ origin: from, destination: to, via, order: 'given', when }), {
      initialProps: undefined as string | undefined,
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(f).toHaveBeenCalledTimes(1);
    rerender('2026-10-18T14:30');
    await waitFor(() => expect(f).toHaveBeenCalledTimes(2));
    expect(bodies(f)[1].when).toBe('2026-10-18T14:30');
  });
});
