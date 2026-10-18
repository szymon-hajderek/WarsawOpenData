import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { ColorModeProvider } from './colorMode';
import { HistoryProvider } from './history/HistoryProvider';
import { PreferencesProvider } from './preferences/PreferencesProvider';
import { BUS_1002_TRACK } from './test/busTrack';
import { DESTINATION, NEAREST_BUSES, onboardRoute, ROUTE_119, seeded, WALK_START, withNoise } from './test/tripFixtures';
import type { LatLng } from './types';

// The map (Leaflet + MapLibre) does not run in jsdom and is not what is tested here.
vi.mock('./components/MapView', () => ({ default: () => null }));

const NEW_DESTINATION: LatLng = [52.1975, 21.0605];

// ------------------------------------------------------------------ fake GPS (every watcher gets every fix)
let watchers = new Map<number, PositionCallback>();
let nextWatch = 1;
function installGeolocation() {
  watchers = new Map();
  const geo = {
    watchPosition: (ok: PositionCallback) => {
      const id = nextWatch++;
      watchers.set(id, ok);
      return id;
    },
    clearWatch: (id: number) => watchers.delete(id),
    getCurrentPosition: () => undefined,
  };
  Object.defineProperty(navigator, 'geolocation', { value: geo, configurable: true });
}
function fix(p: LatLng, tSec: number) {
  const pos = { coords: { latitude: p[0], longitude: p[1], accuracy: 8 }, timestamp: tSec * 1000 } as GeolocationPosition;
  act(() => watchers.forEach((cb) => cb(pos)));
}

// ------------------------------------------------------------------ fake backend (answers follow data/API.md)
interface Call {
  url: string;
  body: Record<string, unknown> | null;
}
let calls: Call[] = [];
let onboardAnswer: 'route' | '404' = 'route';
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

function installBackend() {
  calls = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as Record<string, unknown>) : null;
      calls.push({ url, body });
      if (url.includes('/api/live/nearest-buses')) return json(NEAREST_BUSES);
      if (url.includes('/api/geocode')) {
        return json(
          url.includes('Nowy')
            ? [{ id: 'osm:node:2', label: 'Nowy cel', position: NEW_DESTINATION }]
            : [{ id: 'osm:node:1', label: 'Cel podróży', position: DESTINATION }],
        );
      }
      if (url.includes('/api/routes')) {
        if (body?.onboard) return onboardAnswer === '404' ? json({ detail: 'vehicle not found' }, 404) : json([onboardRoute(NEW_DESTINATION)]);
        const to = body?.to as { label?: string } | undefined;
        return json(to?.label === 'Nowy cel' ? [{ ...onboardRoute(NEW_DESTINATION), id: 'pt-gps', title: 'Z GPS' }] : [ROUTE_119]);
      }
      if (url.includes('/api/live/route-delays')) return json({});
      return json({ detail: 'not found' }, 404);
    }),
  );
}

/** The panel of a `SnapSheet` (found by its drag handle). */
async function findSheet(name: string): Promise<HTMLElement> {
  const handle = await screen.findByRole('button', { name: `${name}: przeciągnij, aby zmienić wysokość` }, { timeout: 3000 });
  return handle.closest('.MuiPaper-root') as HTMLElement;
}

const lastOf = <T,>(items: T[]): T => items[items.length - 1];
const routeCalls = () => calls.filter((c) => c.url.includes('/api/routes'));

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

async function chooseDestination(query: string, label: string) {
  const user = userEvent.setup();
  const field = screen.getByPlaceholderText('Dokąd jedziesz?');
  await user.clear(field);
  await user.type(field, query);
  fireEvent.click(await screen.findByText(label, {}, { timeout: 3000 }));
}

/** Start screen -> destination -> route list -> details -> "Rozpocznij przejazd". */
async function startTrip() {
  renderApp();
  fix(WALK_START, BUS_1002_TRACK[0].t - 60);
  await waitFor(() => expect((screen.getByPlaceholderText('Skąd jedziesz?') as HTMLInputElement).value).toBe('Twoja lokalizacja'));
  await chooseDestination('Cel', 'Cel podróży');
  fireEvent.click(await screen.findByRole('button', { name: /Wybierz tę trasę/ }, { timeout: 3000 }));
  fireEvent.click(await screen.findByRole('button', { name: /Rozpocznij przejazd/ }));
  await findSheet('Aktywny przejazd');
}

/** The user rides bus-1002: its recorded positions with up to 20 m of GPS error. */
function ride(fromIndex: number, toIndex: number) {
  const rnd = seeded(42);
  for (const p of BUS_1002_TRACK.slice(fromIndex, toIndex + 1)) fix(withNoise([p.lat, p.lon], 20, rnd), p.t);
}

describe('active trip', () => {
  beforeEach(() => {
    localStorage.clear();
    installGeolocation();
    installBackend();
    onboardAnswer = 'route';
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('follows the recorded ride, detects the bus, plans a new destination from it and replaces the route', async () => {
    await startTrip();
    expect(screen.getByTestId('next-step')).toHaveTextContent('Idź do: Grochowska 01');

    ride(1, 6);
    expect(screen.getByTestId('next-step')).toHaveTextContent('Wysiadasz na: Rondo Wiatraczna 02');
    const current = (await findSheet('Aktywny przejazd')).querySelector('[aria-current="step"]');
    expect(current).toHaveTextContent('Autobus 119 do: Rondo Wiatraczna 02');

    // "W jakim pojeździe jestem?" uses the trip's own track: the last 3 recorded points, at least 8 s apart
    fireEvent.click(screen.getByRole('button', { name: 'W jakim pojeździe jestem?' }));
    const sheet = await findSheet('Okienko pojazdu');
    await within(sheet).findAllByText(/119/);
    const detection = lastOf(calls.filter((c) => c.url.includes('nearest-buses')))!;
    const points = detection.body!.points as { time_ms: number }[];
    expect(points).toHaveLength(3);
    expect(points[2].time_ms).toBe(BUS_1002_TRACK[6].t * 1000);
    for (let i = 1; i < points.length; i++) expect(points[i].time_ms - points[i - 1].time_ms).toBeGreaterThanOrEqual(8000);
    expect(within(sheet).getByText(/175/)).toBeInTheDocument(); // the other candidates are offered too

    fireEvent.click(within(sheet).getByRole('button', { name: /Jadę tą linią/ }));
    await screen.findByText(/Jedziesz: Autobus 119/);

    // new destination: the start is the vehicle, the request carries `onboard`
    fireEvent.click(screen.getByRole('button', { name: 'Zmień cel' }));
    await waitFor(() =>
      expect((screen.getByPlaceholderText('Skąd jedziesz?') as HTMLInputElement).value).toBe('Z pojazdu: 119 (następne przystanki)'),
    );
    await chooseDestination('Nowy', 'Nowy cel');
    await waitFor(() => expect(lastOf(routeCalls())!.body!.onboard).toEqual({ vehicleId: 'bus-1002' }));
    fireEvent.click(await screen.findByRole('button', { name: /Wybierz tę trasę/ }, { timeout: 3000 }));

    // still in the active trip, now on the new route (its first leg = the ride on the current bus)
    await findSheet('Aktywny przejazd');
    expect(screen.getByTestId('next-step')).toHaveTextContent('Wysiadasz na: Wiatraczna 05');
    expect(screen.queryByText('Rondo Wiatraczna 02', { exact: false })).not.toBeInTheDocument();
  }, 20_000);

  it('says "Zboczyłeś z trasy" far from the route and offers a new route', async () => {
    await startTrip();
    ride(1, 3);
    const p = BUS_1002_TRACK[3];
    fix([p.lat + 400 / 111_320, p.lon], p.t + 10);
    expect(await screen.findByText('Zboczyłeś z trasy')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Zmień trasę' }));
    // no vehicle confirmed: the new search starts at the GPS position and keeps the destination
    await waitFor(() => expect((screen.getByPlaceholderText('Skąd jedziesz?') as HTMLInputElement).value).toBe('Twoja lokalizacja'));
    expect((screen.getByPlaceholderText('Dokąd jedziesz?') as HTMLInputElement).value).toBe('Cel podróży');
  }, 20_000);

  it('vehicle not found (404): plans from the GPS position with a short note', async () => {
    onboardAnswer = '404';
    await startTrip();
    ride(1, 6);
    fireEvent.click(screen.getByRole('button', { name: 'W jakim pojeździe jestem?' }));
    const sheet = await findSheet('Okienko pojazdu');
    await within(sheet).findAllByText(/119/);
    fireEvent.click(within(sheet).getByRole('button', { name: /Jadę tą linią/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Zmień cel' }));
    await chooseDestination('Nowy', 'Nowy cel');

    expect(await screen.findByText('Nie znaleziono pojazdu. Planuję od Twojej lokalizacji.')).toBeInTheDocument();
    await waitFor(() => expect((screen.getByPlaceholderText('Skąd jedziesz?') as HTMLInputElement).value).toBe('Twoja lokalizacja'));
    const last = lastOf(routeCalls())!.body!;
    expect(last.onboard).toBeUndefined();
    expect((last.from as { id: string }).id).toBe('current-location');
    fireEvent.click(await screen.findByRole('button', { name: /Wybierz tę trasę/ }, { timeout: 3000 }));
    await findSheet('Aktywny przejazd');
  }, 20_000);
});
