import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App';
import { ColorModeProvider } from './colorMode';
import { HistoryProvider } from './history/HistoryProvider';
import { PreferencesProvider } from './preferences/PreferencesProvider';
import { requestLinePopup } from './api/vehicle';
import { NEAREST_BUSES } from './test/tripFixtures';

// The map (Leaflet + MapLibre) does not run in jsdom; the bus button is reached through `requestLinePopup`.
vi.mock('./components/MapView', () => ({ default: () => null }));

const HANDLE = 'Okienko pojazdu: przeciągnij, aby zmienić wysokość';
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

/** Answer of `POST /api/live/nearest-buses` for the test. */
let answer: () => Response;
let detections = 0;

function install(withLocation: boolean) {
  detections = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/live/nearest-buses')) {
        detections++;
        return answer();
      }
      return json({ detail: 'not found' }, 404);
    }),
  );
  const geo = {
    watchPosition: (ok: PositionCallback, fail?: PositionErrorCallback) => {
      setTimeout(() =>
        withLocation
          ? ok({ coords: { latitude: 52.2297, longitude: 21.0122, accuracy: 8 }, timestamp: Date.now() } as GeolocationPosition)
          : fail?.({ code: 1, message: 'denied' } as GeolocationPositionError),
      );
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

/** Waits until the automatic detection has answered and the app has rendered its result. */
async function settle(expectDetection = true) {
  if (expectDetection) await waitFor(() => expect(detections).toBeGreaterThan(0));
  await act(async () => {
    await new Promise((r) => setTimeout(r, 50));
  });
}

const candidate = (id: string, line: string, direction: string, rmse: number) => ({
  id,
  vehicle: id.slice(4),
  line,
  brigade: '1',
  mode: 'bus',
  direction,
  rmse_m: rmse,
});

describe('vehicle popup at start', () => {
  beforeEach(() => localStorage.clear());

  it('shows nothing when no vehicle is detected, and the bus button opens it with an explanation', async () => {
    install(true);
    answer = () => json({ candidates: [], lines: ['131'], updated_at: 1 });
    renderApp();
    await settle();
    expect(screen.queryByRole('button', { name: HANDLE })).toBeNull();

    act(() => requestLinePopup());
    await screen.findByRole('button', { name: HANDLE });
    expect(await screen.findByText(/Nie wykryto pojazdu w pobliżu/)).toBeInTheDocument();
  });

  it('shows nothing without a location', async () => {
    install(false);
    answer = () => json(NEAREST_BUSES);
    renderApp();
    await settle(false);
    expect(detections).toBe(0); // no position: nothing is sent
    expect(screen.queryByRole('button', { name: HANDLE })).toBeNull();
  });

  it('shows nothing when live data is unavailable (503)', async () => {
    install(true);
    answer = () => json({ detail: 'no live data' }, 503);
    renderApp();
    await settle();
    expect(screen.queryByRole('button', { name: HANDLE })).toBeNull();
  });

  it('shows nothing when the backend is offline', async () => {
    install(true);
    answer = () => json({ detail: 'boom' }, 500);
    renderApp();
    await settle();
    expect(screen.queryByRole('button', { name: HANDLE })).toBeNull();
  });

  it('one confident vehicle: a collapsed bar that expands to the full sheet', async () => {
    install(true);
    answer = () =>
      json({
        candidates: [candidate('bus-1', '131', 'Sadyba', 22), candidate('bus-2', '175', 'Lotnisko', 300)],
        lines: ['131', '175'],
        updated_at: 1,
      });
    renderApp();
    const handle = await screen.findByRole('button', { name: HANDLE });
    expect(handle).toHaveAttribute('aria-expanded', 'false');
    expect(within(handle).getByLabelText('Wykryliśmy, że jedziesz linią 131 → Sadyba')).toBeInTheDocument();
    expect(within(handle).getByText('Zmień')).toBeInTheDocument();
    expect(screen.queryByText('W jakim pojeździe jesteś?')).toBeNull();

    fireEvent.keyDown(handle, { key: 'Enter' });
    expect(await screen.findByText('W jakim pojeździe jesteś?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Jadę tą linią: Autobus 131/ })).toBeInTheDocument();
    expect(screen.getByLabelText('Inna linia')).toBeInTheDocument();
    expect(screen.getByText('Autobus 175')).toBeInTheDocument();
  });

  it('several plausible vehicles: a collapsed question bar, not the big sheet', async () => {
    install(true);
    answer = () =>
      json({
        candidates: [candidate('bus-1', '131', 'Sadyba', 40), candidate('bus-2', '175', 'Lotnisko', 55)],
        lines: ['131', '175'],
        updated_at: 1,
      });
    renderApp();
    const handle = await screen.findByRole('button', { name: HANDLE });
    expect(handle).toHaveAttribute('aria-expanded', 'false');
    expect(within(handle).getByLabelText('Czy jedziesz tym pojazdem? Autobus 131')).toBeInTheDocument();
    expect(screen.queryByText('W jakim pojeździe jesteś?')).toBeNull();
    fireEvent.keyDown(handle, { key: 'Enter' });
    expect(await screen.findByText('W jakim pojeździe jesteś?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Jadę tą linią: Autobus 131/ })).toBeInTheDocument();
  });

  it('a bus standing at the user position (RMSE ~0, e.g. in a jam) is the confident bar', async () => {
    install(true);
    answer = () =>
      json({ candidates: [candidate('bus-9', '26', 'Wiatraczna', 3), candidate('bus-8', '9', 'Gocław', 260)], lines: ['26', '9'], updated_at: 1 });
    renderApp();
    const handle = await screen.findByRole('button', { name: HANDLE });
    expect(handle).toHaveAttribute('aria-expanded', 'false');
    expect(within(handle).getByLabelText('Wykryliśmy, że jedziesz linią 26 → Wiatraczna')).toBeInTheDocument();
  });

  it('nothing plausible (best match far away): no bar at all', async () => {
    install(true);
    answer = () => json({ candidates: [candidate('bus-1', '131', 'Sadyba', 450)], lines: ['131'], updated_at: 1 });
    renderApp();
    await settle();
    expect(screen.queryByRole('button', { name: HANDLE })).toBeNull();
  });
});
