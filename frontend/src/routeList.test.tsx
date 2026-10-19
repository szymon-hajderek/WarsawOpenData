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

const OTHER = { ...ROUTE_119, id: 'pt-119-b', durationMin: ROUTE_119.durationMin + 5 };
/** What `POST /api/routes` answers; a test may change it between searches. */
let routesAnswer: unknown[] = [ROUTE_119];

function install() {
  routesAnswer = [ROUTE_119];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/live/nearest-buses')) return json(NEAREST_BUSES);
      if (url.includes('/api/geocode')) return json([{ id: 'osm:node:1', label: 'Cel podróży', position: DESTINATION }]);
      if (url.includes('/api/routes')) return json(routesAnswer);
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
  await screen.findByText('Wybierz trasę');
}

/** Opens the filter sheet, picks a sort and a walking limit, and closes it. */
async function setFilters() {
  fireEvent.click(screen.getByRole('button', { name: 'Filtry' }));
  const sheet = await screen.findByRole('presentation');
  fireEvent.click(within(sheet).getByText('Najmniej przesiadek'));
  fireEvent.click(within(sheet).getByText('10 min'));
  fireEvent.click(within(sheet).getByRole('button', { name: /Pokaż trasy/ }));
  await waitFor(() => expect(screen.queryByRole('presentation')).toBeNull());
}

const chip = (label: string) => screen.queryByText(label, { selector: '.MuiChip-deletable > .MuiChip-label' });

describe('sticky filters', () => {
  beforeEach(() => {
    localStorage.clear();
    install();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('stay across a new origin, a travel mode switch and a new departure', async () => {
    renderApp();
    await searchDestination();
    await setFilters();
    expect(chip('Najmniej przesiadek')).toBeInTheDocument();
    expect(chip('Pieszo do 10 min')).toBeInTheDocument();

    // a new origin (swap start and destination)
    fireEvent.click(screen.getByRole('button', { name: 'Zamień start z celem' }));
    await screen.findByText('Wybierz trasę');
    expect(chip('Najmniej przesiadek')).toBeInTheDocument();

    // walking: the transit filters do not apply (hidden); back to transit: they are still there
    const modes = screen.getByRole('group', { name: 'Sposób podróży' });
    fireEvent.click(within(modes).getByText('Pieszo'));
    await waitFor(() => expect(chip('Najmniej przesiadek')).toBeNull());
    fireEvent.click(within(modes).getByText('Komunikacja'));
    await waitFor(() => expect(chip('Najmniej przesiadek')).toBeInTheDocument());
    expect(chip('Pieszo do 10 min')).toBeInTheDocument();

    // a new departure time
    fireEvent.click(screen.getByText('Wyjazd: Teraz'));
    const dialog = await screen.findByRole('dialog', { name: 'Godzina wyjazdu' });
    fireEvent.click(within(dialog).getByText('Jutro'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Gotowe' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Godzina wyjazdu' })).toBeNull());
    expect(chip('Najmniej przesiadek')).toBeInTheDocument();
    expect(chip('Pieszo do 10 min')).toBeInTheDocument();
    await act(async () => undefined);
  });

  it('"Wyczyść filtry" resets them', async () => {
    renderApp();
    await searchDestination();
    await setFilters();
    expect(chip('Najmniej przesiadek')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Filtry' }));
    const sheet = await screen.findByRole('presentation');
    fireEvent.click(within(sheet).getByRole('button', { name: 'Wyczyść filtry' }));
    fireEvent.click(within(sheet).getByRole('button', { name: /Pokaż trasy/ }));
    await waitFor(() => expect(chip('Najmniej przesiadek')).toBeNull());
    expect(chip('Pieszo do 10 min')).toBeNull();
    await act(async () => undefined);
  });
});

const routeCalls = () =>
  (vi.mocked(fetch).mock.calls as unknown as [string, RequestInit][]).filter(([url]) => String(url).includes('/api/routes'));
const routeBody = (call: [string, RequestInit]) => JSON.parse(String(call[1].body));
const option = (id: string) => document.querySelector(`[data-route-id="${id}"]`) as HTMLElement;

describe('"Odśwież trasy"', () => {
  beforeEach(() => {
    localStorage.clear();
    install();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends the same search again (no `when` = a new now) and keeps the selected route', async () => {
    renderApp();
    routesAnswer = [ROUTE_119, OTHER];
    await searchDestination();
    await waitFor(() => expect(option('pt-119-b')).toBeTruthy());
    fireEvent.click(option('pt-119-b'));
    expect(option('pt-119-b')).toHaveAttribute('aria-pressed', 'true');

    const before = routeCalls().length;
    const refresh = screen.getByRole('button', { name: 'Odśwież trasy' });
    fireEvent.click(refresh);
    await waitFor(() => expect(routeCalls().length).toBe(before + 1));
    const calls = routeCalls();
    const [prev, next] = [routeBody(calls[before - 1]), routeBody(calls[before])];
    expect(next).toEqual(prev);
    expect(next).not.toHaveProperty('when'); // "Teraz": the backend plans from its own, new now
    await waitFor(() => expect(screen.getByRole('button', { name: 'Odśwież trasy' })).not.toBeDisabled());
    expect(option('pt-119-b')).toHaveAttribute('aria-pressed', 'true');

    // the selected route is gone from the new answer: the first one is selected
    routesAnswer = [ROUTE_119];
    fireEvent.click(screen.getByRole('button', { name: 'Odśwież trasy' }));
    await waitFor(() => expect(option('pt-119-b')).toBeNull());
    expect(option('pt-119-a')).toHaveAttribute('aria-pressed', 'true');
    await act(async () => undefined);
  });

  it('keeps a chosen departure time', async () => {
    renderApp();
    await searchDestination();
    fireEvent.click(screen.getByText('Wyjazd: Teraz'));
    const dialog = await screen.findByRole('dialog', { name: 'Godzina wyjazdu' });
    fireEvent.click(within(dialog).getByText('Jutro'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Gotowe' }));
    await waitFor(() => expect(routeBody(routeCalls()[routeCalls().length - 1])).toHaveProperty('when'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Odśwież trasy' })).not.toBeDisabled());

    const before = routeCalls().length;
    fireEvent.click(screen.getByRole('button', { name: 'Odśwież trasy' }));
    await waitFor(() => expect(routeCalls().length).toBe(before + 1));
    const calls = routeCalls();
    expect(routeBody(calls[before]).when).toBe(routeBody(calls[before - 1]).when);
    await act(async () => undefined);
  });
});
