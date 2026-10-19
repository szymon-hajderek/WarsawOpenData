import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  applyListFilters,
  applyOverrides,
  DEFAULT_FILTERS,
  DEFAULT_PREFERENCES,
  routeSearchBody,
  sanitizeStored,
  type Preferences,
} from './model';
import { fetchRouteOptions } from '../api/routes';
import type { RouteOption } from '../types';

const noMetro: Preferences = { ...DEFAULT_PREFERENCES, excludedModes: ['metro'] };

const option = (id: string, mode: RouteOption['legs'][number]['mode']): RouteOption => ({
  id,
  title: id,
  legs: [{ mode, from: 'A', to: 'B', durationMin: 10, distanceM: 3000, path: [[52.2, 21.0], [52.23, 21.0]] }],
  departure: '10:00',
  arrival: '10:10',
  durationMin: 10,
  distanceM: 3000,
  walkDistance: 0,
  bikeDistance: 0,
  transfers: 0,
  tags: [],
});

describe('excluded means of transport', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('the preference is sent as excludeModes', () => {
    expect(routeSearchBody(DEFAULT_PREFERENCES).excludeModes).toEqual([]);
    expect(routeSearchBody(noMetro).excludeModes).toEqual(['metro']);
  });

  it('the filter chips override the preference for this search', () => {
    // all five chips on: nothing excluded even though the preference excludes metro
    expect(routeSearchBody(noMetro, ['bus', 'tram', 'metro', 'rail', 'veturilo']).excludeModes).toEqual([]);
    expect(routeSearchBody(noMetro, ['bus', 'metro']).excludeModes).toEqual(['tram', 'rail', 'veturilo']);
    expect(routeSearchBody(noMetro, null).excludeModes).toEqual(['metro']);
  });

  it('a time rule can override the preference', () => {
    const night = applyOverrides(DEFAULT_PREFERENCES, { excludedModes: ['veturilo'] });
    expect(routeSearchBody(night).excludeModes).toEqual(['veturilo']);
  });

  it('is stored with the preferences (unknown values dropped)', () => {
    const stored = sanitizeStored({ base: { excludedModes: ['rail', 'boat'] } });
    expect(stored.base.excludedModes).toEqual(['rail']);
    expect(sanitizeStored({}).base.excludedModes).toEqual([]);
  });

  it('the route list is no longer filtered by mode in the browser', () => {
    const list = [option('m', 'metro'), option('b', 'bus')];
    const visible = applyListFilters(list, noMetro, { ...DEFAULT_FILTERS, modes: ['bus'] });
    expect(visible.map((o) => o.id).sort()).toEqual(['b', 'm']);
  });

  it('the request body carries excludeModes', async () => {
    const fetchSpy = vi.fn(async () => new Response('[]'));
    vi.stubGlobal('fetch', fetchSpy);
    const place = (id: string, lat: number) => ({ id, label: id, position: [lat, 21.0] as [number, number] });
    await fetchRouteOptions({ from: place('a', 52.2), to: place('b', 52.25), profile: 'standard', search: routeSearchBody(noMetro, ['bus']) });
    const init = (fetchSpy.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(JSON.parse(init.body as string).excludeModes).toEqual(['tram', 'metro', 'rail', 'veturilo']);
  });
});
