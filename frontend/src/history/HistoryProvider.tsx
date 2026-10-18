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
import { journeySubmission, logJourney, type JourneySelection, type JourneySubmission } from '../api/journeys';
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
const SHARING_KEY = 'journey-statistics-enabled';
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
 * only the selected whole-trip endpoint references after explicit completion.
 */
export function HistoryProvider({ children }: { children: ReactNode }) {
  const [records, setRecords] = useState<TripRecord[]>(loadRecords);
  const [summary, setSummary] = useState<SpeedSummary>(() => localSummary(loadRecords()));
  const [shareJourneys, setSharing] = useState(loadSharing);
  const sharing = useRef(shareJourneys);
  const submissions = useRef(new Set<AbortController>());

  const [status, setStatus] = useState<TrackerStatus>('idle');
  const [elapsedS, setElapsedS] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const points = useRef<TrackPoint[]>([]);
  const ride = useRef<{
    legs: PlannedLeg[];
    walkAs: 'walking' | 'wheelchair';
    startedAt: number;
    journey?: JourneySubmission;
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
      submissions.current.forEach((controller) => controller.abort());
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
    const pending = submissions.current;
    return () => {
      stopRecording();
      pending.forEach((controller) => controller.abort());
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
        legs, walkAs, startedAt: Date.now(),
        journey: sharing.current && journey ? journeySubmission(journey) : undefined,
      };
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
          if (ride.current) ride.current.journey = undefined;
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
    const track = points.current;
    if (journey && sharing.current && track.length >= 2 && track[track.length - 1].t > track[0].t) {
      const controller = new AbortController();
      submissions.current.add(controller);
      // Independent of speed-history success, including transit-only trips with no speed records.
      void logJourney(journey, controller.signal).finally(() => submissions.current.delete(controller));
    }
    if (ride.current) ride.current.journey = undefined;
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
