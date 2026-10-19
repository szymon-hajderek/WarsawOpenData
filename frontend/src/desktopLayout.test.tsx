import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { ColorModeProvider } from './colorMode';
import { HistoryProvider } from './history/HistoryProvider';
import { PreferencesProvider } from './preferences/PreferencesProvider';
import { DESTINATION, NEAREST_BUSES, ROUTE_119, WALK_START } from './test/tripFixtures';
import { openSearchCard } from './test/searchCard';

// The map (Leaflet + MapLibre) does not run in jsdom and is not what is tested here.
vi.mock('./components/MapView', () => ({ default: () => null }));

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const hhmm = (d: Date) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

/** A screen `width` px wide: `matchMedia` answers the min-width / max-width queries MUI's `useMediaQuery` sends. */
function setScreenWidth(width: number) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) => {
      const min = /min-width:\s*([\d.]+)px/.exec(query);
      const max = /max-width:\s*([\d.]+)px/.exec(query);
      const matches = (!min || width >= Number(min[1])) && (!max || width <= Number(max[1]));
      return { matches, media: query, onchange: null, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false };
    },
  );
}

function install() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/live/nearest-buses')) return json(NEAREST_BUSES);
      if (url.includes('/api/geocode')) return json([{ id: 'osm:node:1', label: 'Cel podróży', position: DESTINATION }]);
      if (url.includes('/api/routes')) return json([{ ...ROUTE_119, departure: hhmm(new Date()) }]);
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

async function searchDestination() {
  await openSearchCard();
  await waitFor(() => expect((screen.getByPlaceholderText('Skąd jedziesz?') as HTMLInputElement).value).toBe('Twoja lokalizacja'));
  const user = userEvent.setup();
  await user.type(screen.getByPlaceholderText('Dokąd jedziesz?'), 'Cel');
  fireEvent.click(await screen.findByText('Cel podróży', {}, { timeout: 3000 }));
}

const dragHandles = () => screen.queryAllByRole('button', { name: /przeciągnij, aby zmienić wysokość/ });

describe('layout', () => {
  beforeEach(() => {
    localStorage.clear();
    install();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('desktop (1440 px): one side panel with the search card and the route list, no drag handles', async () => {
    setScreenWidth(1440);
    renderApp();
    const panel = await screen.findByRole('complementary', { name: 'Panel wyszukiwania' });
    await searchDestination();

    expect(await within(panel).findByText('Wybierz trasę')).toBeInTheDocument();
    expect(within(panel).getByPlaceholderText('Dokąd jedziesz?')).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: /Wybierz tę trasę/ })).toBeInTheDocument();
    expect(dragHandles()).toHaveLength(0);

    // route details in the same panel, with the back button
    fireEvent.click(within(panel).getByRole('button', { name: /Wybierz tę trasę/ }));
    expect(await within(panel).findByText('Szczegóły trasy')).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: 'Wróć do wyboru trasy' })).toBeInTheDocument();
    expect(dragHandles()).toHaveLength(0);
  });

  it('phone (430 px): no side panel, the draggable sheets as before', async () => {
    setScreenWidth(430);
    renderApp();
    await searchDestination();
    expect(await screen.findByRole('button', { name: 'Lista tras: przeciągnij, aby zmienić wysokość' }, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'Panel wyszukiwania' })).toBeNull();
    await act(async () => undefined);
  });
});
