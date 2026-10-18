import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import SearchCard from './components/SearchCard';
import { useRouteSearch } from './hooks/useRouteSearch';
import { DEFAULT_PREFERENCES, routeSearchBody } from './preferences/model';
import type { Access, TransitAccess } from './travel';
import type { Place } from './types';

const place = (id: string, lat: number): Place => ({ id, label: id, position: [lat, 21.0] });
const from = place('a', 52.2);
const to = place('b', 52.25);
const via: Place[] = [];
const ANSWER = [{ id: 'x', legs: [{ mode: 'bike', durationMin: 5, distanceM: 300, path: [[52.2, 21.0], [52.21, 21.0]] }], tags: [] }];
const okFetch = () => vi.fn(async () => new Response(JSON.stringify(ANSWER)));
const lastBody = (f: ReturnType<typeof okFetch>) =>
  JSON.parse(String((f.mock.calls[f.mock.calls.length - 1] as unknown as [string, RequestInit])[1].body));

describe('transit access: on foot or by the own bike', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([
    ['walk', 'standard', { profile: 'standard' }, false],
    ['walk', 'wheelchair', { profile: 'accessible' }, false],
    ['bike', 'standard', { profile: 'standard', access: 'bike' }, true],
    // the own bike drops the wheelchair profile (the backend refuses the pair)
    ['bike', 'wheelchair', { profile: 'standard', access: 'bike' }, true],
  ] as [TransitAccess, Access, Record<string, string>, boolean][])('%s + %s -> %o', async (transitAccess, access, expected, sendsAccess) => {
    const f = okFetch();
    vi.stubGlobal('fetch', f);
    const search = routeSearchBody(DEFAULT_PREFERENCES, null, transitAccess === 'bike' ? 'standard' : access);
    const { result } = renderHook(() =>
      useRouteSearch({ origin: from, destination: to, via, order: 'given', search, travel: 'transit', access, transitAccess }),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    const body = lastBody(f);
    expect(body).toMatchObject(expected);
    expect(body).not.toHaveProperty('travel');
    if (sendsAccess) {
      expect(body.stepFree).toBe(false);
      expect(body.body.wheelchair).toBe('none');
    } else {
      expect(body).not.toHaveProperty('access');
    }
  });

  it('a street-only trip never sends access', async () => {
    const f = okFetch();
    vi.stubGlobal('fetch', f);
    const { result } = renderHook(() =>
      useRouteSearch({ origin: from, destination: to, via, order: 'given', travel: 'bike', transitAccess: 'bike' }),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(lastBody(f)).toMatchObject({ travel: 'bike' });
    expect(lastBody(f)).not.toHaveProperty('access');
  });
});

describe('"Dojazd" in the search card', () => {
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
    onTravelChange: () => {},
    onAccessChange: () => {},
    access: 'standard' as const,
  };

  it('shown for public transport only; "Rowerem" hides the accessibility choice', () => {
    const onChange = vi.fn();
    const { rerender } = render(<SearchCard {...props} travel="transit" transitAccess="walk" onTransitAccessChange={onChange} />);
    const group = screen.getByRole('group', { name: 'Dojazd:' });
    expect(Array.from(group.children).map((c) => c.textContent)).toEqual(['Pieszo', 'Rowerem']);
    expect(screen.getByRole('group', { name: 'Dostępność' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Rowerem' }));
    expect(onChange).toHaveBeenCalledWith('bike');

    rerender(<SearchCard {...props} travel="transit" transitAccess="bike" onTransitAccessChange={onChange} />);
    expect(screen.getByRole('button', { name: 'Rowerem' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('group', { name: 'Dostępność' })).toBeNull();

    rerender(<SearchCard {...props} travel="walk" transitAccess="bike" onTransitAccessChange={onChange} />);
    expect(screen.queryByRole('group', { name: 'Dojazd:' })).toBeNull();
    expect(screen.getByRole('group', { name: 'Dostępność' })).toBeInTheDocument();
  });
});
