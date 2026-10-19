import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

/** Lets the user move for `ms`: the location track samples every 10 s, automatic detection runs every 5 s. */
async function ride(ms = 35_000) {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 20)); // the first fix arrives (real timeout)
    for (let t = 0; t < ms; t += 5_000) vi.advanceTimersByTime(5_000);
  });
}

/** Waits until the automatic detection has answered and the app has rendered its result. */
async function settle(expectDetection = true) {
  await ride();
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
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ['setInterval', 'Date'] });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

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
    await ride();
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
    await ride();
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
    await ride();
    const handle = await screen.findByRole('button', { name: HANDLE });
    expect(handle).toHaveAttribute('aria-expanded', 'false');
    expect(within(handle).getByLabelText('Wykryliśmy, że jedziesz linią 26 → Wiatraczna')).toBeInTheDocument();
  });

  it('no distance limit: the best match far away is still offered as a question', async () => {
    install(true);
    answer = () =>
      json({ candidates: [candidate('bus-1', '131', 'Sadyba', 450), candidate('bus-2', '175', 'Lotnisko', 500)], lines: ['131'], updated_at: 1 });
    renderApp();
    await ride();
    const handle = await screen.findByRole('button', { name: HANDLE });
    expect(within(handle).getByLabelText('Czy jedziesz tym pojazdem? Autobus 131')).toBeInTheDocument();
  });

  it('one position is not enough; detection repeats, so boarding after opening the app is found', async () => {
    install(true);
    answer = () => json({ candidates: [], lines: ['24'], updated_at: 1 });
    renderApp();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    expect(detections).toBe(0); // only the first fix: no automatic detection yet
    await settle(); // at the stop: nothing found
    expect(screen.queryByRole('button', { name: HANDLE })).toBeNull();
    answer = () =>
      json({ candidates: [candidate('tram-3274', '24', 'Gocławek', 18), candidate('bus-5878', '175', 'Lotnisko', 120)], lines: ['24'], updated_at: 1 });
    await ride(6_000); // boarded: the next automatic detection (every 5 s) finds the tram
    const handle = await screen.findByRole('button', { name: HANDLE });
    expect(within(handle).getByLabelText('Wykryliśmy, że jedziesz linią 24 → Gocławek')).toBeInTheDocument();
  });

  it('"Jadę tą linią" on the start screen makes the vehicle the start of the next search', async () => {
    install(true);
    answer = () =>
      json({ candidates: [candidate('bus-1', '131', 'Sadyba', 22), candidate('bus-2', '175', 'Lotnisko', 300)], lines: ['131'], updated_at: 1 });
    renderApp();
    await ride();
    const handle = await screen.findByRole('button', { name: HANDLE });
    fireEvent.keyDown(handle, { key: 'Enter' });
    fireEvent.click(await screen.findByRole('button', { name: /Jadę tą linią: Autobus 131/ }));
    await waitFor(() => expect(screen.getByLabelText('Skąd jedziesz?')).toHaveValue('Z pojazdu: 131 (następne przystanki)'));
  });

  it('the confirmed vehicle is forgotten once the user has left it (2 checks without it)', async () => {
    install(true);
    answer = () =>
      json({ candidates: [candidate('bus-1', '106', 'Mariensztat', 15), candidate('bus-2', '175', 'Lotnisko', 300)], lines: ['106'], updated_at: 1 });
    renderApp();
    await ride();
    fireEvent.keyDown(await screen.findByRole('button', { name: HANDLE }), { key: 'Enter' });
    fireEvent.click(await screen.findByRole('button', { name: /Jadę tą linią: Autobus 106/ }));
    expect(await screen.findByText('Jedziesz: Autobus 106')).toBeInTheDocument();
    await ride(6_000); // still on board: kept
    expect(screen.getByText('Jedziesz: Autobus 106')).toBeInTheDocument();
    answer = () => json({ candidates: [candidate('bus-2', '175', 'Lotnisko', 40)], lines: ['175'], updated_at: 1 });
    await ride(6_000); // got off: the first check without bus 106 keeps it ...
    expect(screen.getByText('Jedziesz: Autobus 106')).toBeInTheDocument();
    await ride(6_000); // ... the second one forgets it
    await waitFor(() => expect(screen.queryByText('Jedziesz: Autobus 106')).toBeNull());
  }, 15_000);
});
