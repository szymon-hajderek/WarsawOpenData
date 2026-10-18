import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { fetchSummary, fetchTripRecords, localSummary, type PlannedLeg } from '../api/history';
import type { JourneySelection } from '../api/journeys';
import { CITY_SHARING_KEY, cityPoint, cityRoute, forgetJourney, journeyId, logCityEvent, revokeCityConsent } from '../api/cityEvents';
import { formatKmh } from '../preferences/model';
import {
  MAX_RECORDS,
  type SpeedMode,
  type SpeedSummary,
  type TrackPoint,
  type TripRecord,
} from './types';

export type TrackerStatus = 'idle' | 'tracking' | 'saving' | 'done' | 'error';

export interface Tracker {
  status: TrackerStatus;
  /** Seconds since the ride was started. */
  elapsedS: number;
  /** Result or error text to show after the ride. */
  message: string | null;
  /** Starts recording GPS points for a ride along the given legs. */
  start: (legs: PlannedLeg[], walkAs: 'walking' | 'wheelchair', journey?: JourneySelection) => void;
  /** Stops recording and saves the trip (the backend turns the track into records). */
  stop: () => Promise<void>;
  /** Tries to save again after an error. */
  retry: () => Promise<void>;
  /** Hides the result message. */
  dismiss: () => void;
  /** The GPS points of the ride being recorded (memory only, one every 4 s); empty when not recording. */
  track: () => TrackPoint[];
}

interface HistoryValue {
  records: TripRecord[];
  summary: SpeedSummary;
  tracker: Tracker;
  clear: () => void;
  shareJourneys: boolean;
  setShareJourneys: (enabled: boolean) => void;
}

const STORAGE_KEY = 'trip-history';
const SHARING_KEY = CITY_SHARING_KEY;
const SAMPLE_S = 4; // keep a GPS point at most every 4 seconds
const MAX_ACCURACY_M = 100;

const MODE_LABEL: Record<SpeedMode, string> = { walking: 'Pieszo', cycling: 'Rower', wheelchair: 'Wózek' };

const noop = async () => {};
const HistoryContext = createContext<HistoryValue>({
  records: [],
  summary: localSummary([]),
  tracker: { status: 'idle', elapsedS: 0, message: null, start: () => {}, stop: noop, retry: noop, dismiss: () => {}, track: () => [] },
  clear: () => {},
  shareJourneys: false,
  setShareJourneys: () => {},
});

function loadRecords(): TripRecord[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
    return Array.isArray(raw) ? raw.filter((r) => r && typeof r.kmh === 'number' && typeof r.mode === 'string') : [];
  } catch {
    return [];
  }
}

function loadSharing(): boolean {
  try { return localStorage.getItem(SHARING_KEY) === 'true'; } catch { return false; }
}

type WakeLockSentinel = { release: () => Promise<void> };
type WakeLockNavigator = Navigator & { wakeLock?: { request: (type: 'screen') => Promise<WakeLockSentinel> } };

/**
 * The device's trip history and the GPS recorder.
 *
 * Records (no coordinates) are kept in localStorage; the GPS track only lives in memory while a ride is
 * recorded and is sent to the speed-history endpoint once. Separately, opt-in statistics send
 * research events without storing the GPS track. The legacy endpoint counters are no longer submitted.
 */
export function HistoryProvider({ children }: { children: ReactNode }) {
  const [records, setRecords] = useState<TripRecord[]>(loadRecords);
  const [summary, setSummary] = useState<SpeedSummary>(() => localSummary(loadRecords()));
  const [shareJourneys, setSharing] = useState(loadSharing);
  const sharing = useRef(shareJourneys);

  const [status, setStatus] = useState<TrackerStatus>('idle');
  const [elapsedS, setElapsedS] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const points = useRef<TrackPoint[]>([]);
  const ride = useRef<{
    legs: PlannedLeg[];
    walkAs: 'walking' | 'wheelchair';
    startedAt: number;
    journey?: Record<string, unknown>;
    route?: JourneySelection['route'];
  } | null>(null);
  const watchId = useRef<number | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const wakeLock = useRef<WakeLockSentinel | null>(null);

  const setShareJourneys = useCallback((enabled: boolean) => {
    sharing.current = enabled;
    setSharing(enabled);
    try { localStorage.setItem(SHARING_KEY, String(enabled)); } catch { /* storage unavailable */ }
    if (!enabled) {
      if (ride.current) ride.current.journey = undefined;
      revokeCityConsent();
    }
  }, []);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === SHARING_KEY || event.key === null) setShareJourneys(event.newValue === 'true');
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [setShareJourneys]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    } catch {
      /* storage unavailable */
    }
    let cancelled = false;
    fetchSummary(records).then((s) => !cancelled && setSummary(s));
    return () => {
      cancelled = true;
    };
  }, [records]);

  const stopRecording = useCallback(() => {
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    watchId.current = null;
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    wakeLock.current?.release().catch(() => {});
    wakeLock.current = null;
  }, []);

  useEffect(() => {
    const interrupt = () => {
      const current = ride.current;
      if (current?.journey) {
        void logCityEvent('journey_interrupted', { ...current.journey, elapsed_s: (Date.now() - current.startedAt) / 1000 });
        current.journey = undefined;
      }
      if (current?.route) forgetJourney(current.route);
    };
    window.addEventListener('pagehide', interrupt);
    return () => {
      stopRecording();
      window.removeEventListener('pagehide', interrupt);
      interrupt();
    };
  }, [stopRecording]);

  const start = useCallback<Tracker['start']>(
    (legs, walkAs, journey) => {
      if (status === 'tracking' || status === 'saving') return;
      if (!navigator.geolocation) {
        setStatus('error');
        setMessage('Ta przeglądarka nie udostępnia lokalizacji.');
        return;
      }
      points.current = [];
      ride.current = {
        legs, walkAs, startedAt: Date.now(), route: journey?.route,
        journey: sharing.current && journey ? {
          journey_id: journey.route ? journeyId(journey.route) : crypto.randomUUID(),
          origin: cityPoint(journey.from), destination: cityPoint(journey.to),
          ...(journey.route ? cityRoute(journey.route) : { legs: [] }),
        } : undefined,
      };
      if (ride.current.journey) void logCityEvent('journey_started', ride.current.journey);
      setElapsedS(0);
      setMessage(null);
      setStatus('tracking');

      watchId.current = navigator.geolocation.watchPosition(
        (pos) => {
          const t = pos.timestamp / 1000;
          const last = points.current[points.current.length - 1];
          if (pos.coords.accuracy > MAX_ACCURACY_M || (last && t - last.t < SAMPLE_S)) return;
          points.current.push({ lat: pos.coords.latitude, lon: pos.coords.longitude, t });
        },
        () => {
          stopRecording();
          if (ride.current?.journey) void logCityEvent('journey_interrupted', {
            ...ride.current.journey, elapsed_s: (Date.now() - ride.current.startedAt) / 1000,
          });
          if (ride.current) ride.current.journey = undefined;
          if (ride.current?.route) forgetJourney(ride.current.route);
          setStatus('error');
          setMessage('Nie udało się ustalić lokalizacji. Sprawdź zgodę na lokalizację i spróbuj ponownie.');
        },
        { enableHighAccuracy: true, maximumAge: 0 },
      );
      timer.current = setInterval(() => setElapsedS(Math.round((Date.now() - (ride.current?.startedAt ?? Date.now())) / 1000)), 1000);
      // keep the screen on: a browser cannot record in the background
      (navigator as WakeLockNavigator).wakeLock?.request('screen').then((l) => (wakeLock.current = l)).catch(() => {});
    },
    [status, stopRecording],
  );

  const save = useCallback(async () => {
    const r = ride.current;
    if (!r) return;
    setStatus('saving');
    try {
      const fresh = await fetchTripRecords(points.current, r.legs, r.walkAs);
      if (fresh.length === 0) {
        setMessage('Przejazd był za krótki lub nie pasował do trasy, więc go nie zapisano.');
      } else {
        setRecords((prev) => [...prev, ...fresh].slice(-MAX_RECORDS));
        setMessage(`Zapisano: ${fresh.map((x) => `${MODE_LABEL[x.mode]} ${formatKmh(x.kmh)}`).join(' · ')}`);
      }
      points.current = [];
      ride.current = null;
      setStatus('done');
    } catch {
      setStatus('error');
      setMessage('Nie udało się zapisać przejazdu (brak połączenia z serwerem). Spróbuj ponownie.');
    }
  }, []);

  const stop = useCallback(async () => {
    if (status !== 'tracking') return;
    stopRecording();
    const journey = ride.current?.journey;
    if (journey && sharing.current) {
      // Explicit app action, not verified GPS arrival or proof of a Veturilo rental.
      void logCityEvent('journey_finished', { ...journey, elapsed_s: (Date.now() - ride.current!.startedAt) / 1000 });
    }
    if (ride.current) ride.current.journey = undefined;
    if (ride.current?.route) forgetJourney(ride.current.route);
    await save();
  }, [status, stopRecording, save]);

  const dismiss = useCallback(() => {
    setMessage(null);
    setStatus((s) => (s === 'tracking' || s === 'saving' ? s : 'idle'));
  }, []);

  const clear = useCallback(() => setRecords([]), []);
  const track = useCallback(() => [...points.current], []);

  const tracker = useMemo<Tracker>(
    () => ({ status, elapsedS, message, start, stop, retry: save, dismiss, track }),
    [status, elapsedS, message, start, stop, save, dismiss, track],
  );
  const value = useMemo(
    () => ({ records, summary, tracker, clear, shareJourneys, setShareJourneys }),
    [records, summary, tracker, clear, shareJourneys, setShareJourneys],
  );

  return <HistoryContext.Provider value={value}>{children}</HistoryContext.Provider>;
}

export const useHistory = () => useContext(HistoryContext);
