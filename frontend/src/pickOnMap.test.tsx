import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';
import { ColorModeProvider } from './colorMode';
import { HistoryProvider } from './history/HistoryProvider';
import { PreferencesProvider } from './preferences/PreferencesProvider';
import { NEAREST_BUSES, ROUTE_119, WALK_START } from './test/tripFixtures';
import type { LatLng } from './types';
import { openSearchCard } from './test/searchCard';

/** Where the fake map is tapped. */
const TAP: LatLng = [52.2301, 21.0115];

// The map (Leaflet + MapLibre) does not run in jsdom: a stand-in with buttons for a tap and the long-press menu.
vi.mock('./components/MapView', () => ({
  default: (props: {
    onMapPick?: (p: LatLng) => void;
    onContextPick?: (t: 'origin' | 'destination', p: LatLng) => void;
  }) => (
    <div>
      {props.onMapPick && <button onClick={() => props.onMapPick?.(TAP)}>fake-map-tap</button>}
      {props.onContextPick && <button onClick={() => props.onContextPick?.('destination', TAP)}>fake-map-dotad</button>}
    </div>
  ),
}));

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

let stations: unknown[] = [];

function install() {
  stations = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/live/nearest-buses')) return json(NEAREST_BUSES);
      if (url.includes('/api/stations')) return json(stations);
      if (url.includes('/api/routes')) return json([ROUTE_119]);
      if (url.includes('/api/live/route-delays')) return json({});
      return json({ detail: 'not found' }, 404);
    }),
  );
  const geo = {
    watchPosition: (ok: PositionCallback) => {
      setTimeout(() => ok({ coords: { latitude: WALK_START[0], longitude: WALK_START[1], accuracy: 8 }, timestamp: Date.now() } as GeolocationPosition));
      return 1;
    },
    clearWatch: () => undefined,
    getCurrentPosition: () => undefined,
  };
  Object.defineProperty(navigator, 'geolocation', { value: geo, configurable: true });
}

function renderApp() {
  return render(
    <ColorModeProvider>
      <HistoryProvider>
        <PreferencesProvider>
          <App />
        </PreferencesProvider>
      </HistoryProvider>
    </ColorModeProvider>,
  );
}

const routeBodies = () =>
  (vi.mocked(fetch).mock.calls as unknown as [string, RequestInit][])
    .filter(([url]) => String(url).includes('/api/routes'))
    .map(([, init]) => JSON.parse(String(init.body)));

const destinationInput = () => screen.getByPlaceholderText('Dokąd jedziesz?') as HTMLInputElement;

async function startPickingDestination() {
  await openSearchCard();
  await waitFor(() => expect((screen.getByPlaceholderText('Skąd jedziesz?') as HTMLInputElement).value).toBe('Twoja lokalizacja'));
  fireEvent.mouseDown(destinationInput());
  fireEvent.click(await screen.findByText('Wybierz na mapie'));
  expect(await screen.findByText('Dotknij mapy, aby wybrać punkt')).toBeInTheDocument();
}

describe('pick a place on the map', () => {
  beforeEach(() => {
    localStorage.clear();
    install();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('a tap sets "Punkt na mapie" as the destination and runs the search', async () => {
    renderApp();
    await startPickingDestination();
    fireEvent.click(screen.getByText('fake-map-tap'));

    await waitFor(() => expect(destinationInput().value).toBe('Punkt na mapie'));
    expect(screen.queryByText('Dotknij mapy, aby wybrać punkt')).toBeNull();
    await waitFor(() => expect(routeBodies().length).toBe(1));
    expect(routeBodies()[0].to).toMatchObject({ label: 'Punkt na mapie', position: TAP });
    await act(async () => undefined);
  });

  it('a tap next to a stop takes the stop', async () => {
    stations = [{ id: 'ztm:701307', kind: 'tram_post', name: 'Centrum', position: { lat: 52.2302, lon: 21.01149 } }];
    renderApp();
    await startPickingDestination();
    fireEvent.click(screen.getByText('fake-map-tap'));

    await waitFor(() => expect(destinationInput().value).toBe('Centrum'));
    await waitFor(() => expect(routeBodies().length).toBe(1));
    expect(routeBodies()[0].to).toMatchObject({ id: 'ztm:701307', label: 'Centrum' });
    await act(async () => undefined);
  });

  it('"Anuluj" leaves everything as it was', async () => {
    renderApp();
    await startPickingDestination();
    fireEvent.click(screen.getByRole('button', { name: 'Anuluj' }));

    expect(screen.queryByText('Dotknij mapy, aby wybrać punkt')).toBeNull();
    expect(screen.queryByText('fake-map-tap')).toBeNull();
    expect(destinationInput().value).toBe('');
    expect(routeBodies()).toHaveLength(0);
    await act(async () => undefined);
  });

  it('the long-press menu "Dotąd" sets the destination', async () => {
    renderApp();
    await openSearchCard();
    await waitFor(() => expect((screen.getByPlaceholderText('Skąd jedziesz?') as HTMLInputElement).value).toBe('Twoja lokalizacja'));
    fireEvent.click(screen.getByText('fake-map-dotad'));
    await waitFor(() => expect(destinationInput().value).toBe('Punkt na mapie'));
    await waitFor(() => expect(routeBodies().length).toBe(1));
    await act(async () => undefined);
  });
});
