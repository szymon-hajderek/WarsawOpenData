import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import SearchCard from './components/SearchCard';
import { useRouteSearch } from './hooks/useRouteSearch';
import { DEFAULT_PREFERENCES, routeSearchBody, type Preferences } from './preferences/model';
import { hasAccess, streetMode, TRANSIT_PROFILE, type Access, type TravelMode } from './travel';
import type { Place } from './types';

const place = (id: string, lat: number): Place => ({ id, label: id, position: [lat, 21.0] });
const from = place('a', 52.2);
const to = place('b', 52.25);
const via: Place[] = [];
const ANSWER = [{ id: 'x', legs: [{ mode: 'walk', durationMin: 5, distanceM: 300, path: [[52.2, 21.0], [52.21, 21.0]] }], tags: [] }];
const okFetch = () => vi.fn(async () => new Response(JSON.stringify(ANSWER)));
const lastBody = (f: ReturnType<typeof okFetch>) =>
  JSON.parse(String((f.mock.calls[f.mock.calls.length - 1] as unknown as [string, RequestInit])[1].body));

const chair: Preferences = { ...DEFAULT_PREFERENCES, wheelchair: { ...DEFAULT_PREFERENCES.wheelchair, type: 'manual' } };

describe('main travel modes', () => {
  it('only public transport and walking have an accessibility choice', () => {
    expect(hasAccess('transit')).toBe(true);
    expect(hasAccess('walk')).toBe(true);
    expect(hasAccess('bike')).toBe(false);
  });

  it('maps a main mode + accessibility to a street trip or a transit profile', () => {
    expect(streetMode('transit', 'wheelchair')).toBeNull();
    expect(streetMode('walk', 'standard')).toBe('walk');
    expect(streetMode('walk', 'wheelchair')).toBe('wheelchair');
    expect(streetMode('walk', 'stroller')).toBe('stroller');
    expect(streetMode('bike', 'wheelchair')).toBe('bike');
    expect(TRANSIT_PROFILE).toEqual({ standard: 'standard', wheelchair: 'accessible', stroller: 'stroller' });
  });
});

describe('request of each mode', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const search = routeSearchBody({ ...DEFAULT_PREFERENCES, excludedModes: ['metro'] });

  it.each([
    ['transit', 'standard', { profile: 'standard' }],
    ['transit', 'wheelchair', { profile: 'accessible' }],
    ['transit', 'stroller', { profile: 'stroller' }],
    ['walk', 'standard', { travel: 'walk' }],
    ['walk', 'wheelchair', { travel: 'accessible' }],
    ['walk', 'stroller', { travel: 'stroller' }],
    ['bike', 'standard', { travel: 'bike' }],
    ['bike', 'wheelchair', { travel: 'bike' }],
  ] as [TravelMode, Access, Record<string, string>][])('%s + %s -> %o', async (travel, access, expected) => {
    const f = okFetch();
    vi.stubGlobal('fetch', f);
    const { result } = renderHook(() => useRouteSearch({ origin: from, destination: to, via, order: 'given', search, travel, access }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const body = lastBody(f);
    expect(body).toMatchObject(expected);
    if (travel === 'transit') {
      expect(body).not.toHaveProperty('travel');
      // exclusions only for public transport
      expect(body.excludeModes).toEqual(['metro']);
    } else {
      expect(body).not.toHaveProperty('profile');
      expect(body).not.toHaveProperty('excludeModes');
    }
  });
});

describe('picked accessibility wins over the preferences', () => {
  it('nothing picked: the preferences decide', () => {
    const body = routeSearchBody(chair);
    expect(body.stepFree).toBe(true);
    expect(body.body.wheelchair).toBe('manual');
  });

  it('"Pieszo" (standard) drops the wheelchair and step-free preferences', () => {
    const stepFree = { ...chair, wheelchair: { ...chair.wheelchair, stepFree: true } };
    const body = routeSearchBody(stepFree, null, 'standard');
    expect(body.stepFree).toBe(false);
    expect(body.body.wheelchair).toBe('none');
    expect(body.walkKmh).toBe(routeSearchBody(DEFAULT_PREFERENCES).walkKmh);
  });

  it('stroller: no wheelchair, no step-free flag, the profile pace', () => {
    const body = routeSearchBody(chair, null, 'stroller');
    expect(body.stepFree).toBe(false);
    expect(body.body.wheelchair).toBe('none');
    expect(body.walkKmh).toBeUndefined();
    expect(body.bikeKmh).toBe(0);
  });

  it('wheelchair without a wheelchair preference: step-free, the profile pace', () => {
    const body = routeSearchBody(DEFAULT_PREFERENCES, null, 'wheelchair');
    expect(body.stepFree).toBe(true);
    expect(body.walkKmh).toBeUndefined();
    expect(body.bikeKmh).toBe(0);
  });
});

describe('travel controls in the search card', () => {
  const props = {
    origin: null,
    destination: null,
    stops: [],
    order: 'given' as const,
    currentLocation: null,
    onOriginChange: () => {},
    onDestinationChange: () => {},
    onStopsChange: () => {},
    onOrderChange: () => {},
    onSwap: () => {},
    onLocate: () => {},
  };

  it('three main modes; accessibility for transit and walking, hidden for the bike', () => {
    const onTravel = vi.fn();
    const onAccess = vi.fn();
    const { rerender } = render(<SearchCard {...props} travel="transit" onTravelChange={onTravel} access="standard" onAccessChange={onAccess} />);
    const modes = screen.getByRole('group', { name: 'Sposób podróży' });
    expect(Array.from(modes.children).map((c) => c.textContent)).toEqual(['Komunikacja', 'Pieszo', 'Rower']);
    expect(screen.getByRole('group', { name: 'Dostępność' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Z wózkiem dziecięcym' }));
    expect(onAccess).toHaveBeenCalledWith('stroller');
    fireEvent.click(screen.getByText('Rower'));
    expect(onTravel).toHaveBeenCalledWith('bike');

    rerender(<SearchCard {...props} travel="walk" onTravelChange={onTravel} access="wheelchair" onAccessChange={onAccess} />);
    expect(screen.getByRole('button', { name: 'Na wózku' })).toHaveAttribute('aria-pressed', 'true');

    rerender(<SearchCard {...props} travel="bike" onTravelChange={onTravel} access="standard" onAccessChange={onAccess} />);
    expect(screen.queryByRole('group', { name: 'Dostępność' })).toBeNull();
  });
});
