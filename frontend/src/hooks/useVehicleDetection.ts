import { useCallback, useEffect, useRef, useState } from 'react';
import {
  BUS_POPUP_REQUEST_EVENT,
  detectVehicle,
  manualCandidate,
  requestLinePopup,
  type TrackPoint,
} from '../api/vehicle';
import { watchDelay } from '../api/delay';
import type { VehicleSnap } from '../components/VehicleSheet';
import type { LatLng, VehicleCandidate } from '../types';
import { autoVehicleView } from '../utils/vehicleConfidence';

interface Input {
  position: LatLng | null;
  /** Kept for callers; detection waits for a track of 2+ positions anyway. */
  geoError?: boolean;
  getTrack: () => TrackPoint[];
}

/** Automatic detection runs this often until a vehicle is confirmed (search screen and active trip alike); the first
 * run needs 2 track points (~10 s). The feed changes every ~10 s and one detection costs ~2 ms on the server. */
export const AUTO_DETECT_EVERY_MS = 5_000;
/** After "Nie jadę komunikacją" the automatic detection waits this long (the bus button still works). */
export const AUTO_PAUSE_AFTER_DISMISS_MS = 5 * 60_000;

/**
 * State of the "which vehicle am I in?" window. Detects automatically every AUTO_DETECT_EVERY_MS once the track has at
 * least 2 positions (one position cannot tell a bus from a pedestrian next to it), until a vehicle is confirmed or the
 * window is dismissed (then paused for AUTO_PAUSE_AFTER_DISMISS_MS); and at once when asked through `requestLinePopup()`.
 * So opening the app at the stop and boarding later still finds the vehicle.
 * The automatic detection opens the window only when it found something (`autoVehicleView`): one confident
 * vehicle = the collapsed bar, several plausible ones = the sheet in the middle; nothing / no location / no live
 * data / offline = no window. A detection the user asked for always opens the sheet (with the explanation).
 * After "Jadę tą linią" it polls the delay of that vehicle (`bus-delay` events, `api/delay.ts`) until a new
 * detection or "Nie jadę komunikacją".
 */
export function useVehicleDetection({ position, getTrack }: Input) {
  const [vehicles, setVehicles] = useState<VehicleCandidate[]>([]);
  const [lines, setLines] = useState<string[]>([]);
  const [manual, setManual] = useState<VehicleCandidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [liveUnavailable, setLiveUnavailable] = useState(false);
  const [snap, setSnap] = useState<VehicleSnap>('middle');
  // The window is on screen. Closed until a detection finds something or the user asks for it.
  const [open, setOpen] = useState(false);
  // The running detection was asked for by the user (not the automatic one at start).
  const requested = useRef(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<VehicleCandidate | null>(null);
  const [run, setRun] = useState(0);
  const [delayVehicleId, setDelayVehicleId] = useState<string | null>(null);

  const getTrackRef = useRef(getTrack);
  getTrackRef.current = getTrack;
  const confirmedRef = useRef<VehicleCandidate | null>(null);
  confirmedRef.current = confirmed;
  const openRef = useRef(false);
  openRef.current = open;
  const dismissedAt = useRef(-Infinity);

  useEffect(() => {
    const id = window.setInterval(() => {
      if (confirmedRef.current || Date.now() - dismissedAt.current < AUTO_PAUSE_AFTER_DISMISS_MS) return;
      if (getTrackRef.current().length < 2) return;
      setRun((n) => n + 1);
    }, AUTO_DETECT_EVERY_MS);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const onRequest = () => {
      setRun((n) => n + 1);
      requested.current = true;
      setDelayVehicleId(null);
      setOpen(true);
      setSnap('middle');
    };
    window.addEventListener(BUS_POPUP_REQUEST_EVENT, onRequest);
    return () => window.removeEventListener(BUS_POPUP_REQUEST_EVENT, onRequest);
  }, []);

  useEffect(() => {
    if (run === 0) return;
    const ac = new AbortController();
    setLoading(true);
    // Reads the position at the moment of the run (not a dependency: a new fix must not detect again).
    detectVehicle(getTrackRef.current(), position, ac.signal)
      .then((found) => {
        setVehicles(found.candidates);
        setLines(found.lines);
        setOffline(found.offline);
        setLiveUnavailable(Boolean(found.liveUnavailable));
        setManual(null);
        setSelectedId((prev) => (found.candidates.some((v) => v.id === prev) ? prev : found.candidates[0]?.id ?? null));
        setLoading(false);
        if (!requested.current && autoVehicleView(found) !== 'none' && !openRef.current) {
          setOpen(true);
          setSnap('bar'); // a small collapsed bar; the user expands it (a later detection keeps the user's snap)
        }
      })
      .catch((err) => {
        if (ac.signal.aborted) return;
        console.warn('Vehicle detection failed', err);
        setLoading(false);
      });
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]);

  useEffect(() => (delayVehicleId ? watchDelay(delayVehicleId) : undefined), [delayVehicleId]);

  const selectManualLine = useCallback((line: string) => {
    const v = manualCandidate(line);
    setManual(v);
    setSelectedId(v.id);
  }, []);

  const clearManual = useCallback(() => {
    setManual(null);
    setSelectedId(vehicles[0]?.id ?? null);
  }, [vehicles]);

  const confirm = useCallback(() => {
    const all = manual ? [...vehicles, manual] : vehicles;
    const picked = all.find((v) => v.id === selectedId) ?? null;
    setConfirmed(picked);
    setDelayVehicleId(picked?.id ?? null);
    setSnap('bar');
  }, [manual, vehicles, selectedId]);

  return {
    vehicles,
    lines,
    manual,
    loading,
    offline,
    liveUnavailable,
    snap,
    /** The window is shown (false after "Nie jadę komunikacją" and while nothing was detected automatically). */
    open,
    selectedId,
    confirmed,
    setSnap,
    setSelectedId,
    selectManualLine,
    clearManual,
    confirm,
    dismiss: () => {
      setOpen(false);
      requested.current = false;
      dismissedAt.current = Date.now();
      setConfirmed(null); // "Nie jadę komunikacją": no vehicle to plan from
      setDelayVehicleId(null);
    },
    redetect: requestLinePopup,
    /** Hides the window and keeps the confirmed vehicle (the active trip shows it in its own sheet). */
    hide: () => {
      setOpen(false);
      requested.current = false;
    },
  };
}
