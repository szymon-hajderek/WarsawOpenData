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
  geoError: boolean;
  getTrack: () => TrackPoint[];
}

/**
 * State of the "which vehicle am I in?" window. Detects once after start (first location, or none
 * after a geolocation error), then only when asked through `requestLinePopup()`.
 * The automatic detection opens the window only when it found something (`autoVehicleView`): one confident
 * vehicle = the collapsed bar, several plausible ones = the sheet in the middle; nothing / no location / no live
 * data / offline = no window. A detection the user asked for always opens the sheet (with the explanation).
 * After "Jadę tą linią" it polls the delay of that vehicle (`bus-delay` events, `api/delay.ts`) until a new
 * detection or "Nie jadę komunikacją".
 */
export function useVehicleDetection({ position, geoError, getTrack }: Input) {
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

  useEffect(() => {
    if (position || geoError) setRun((n) => n || 1);
  }, [position, geoError]);

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
    detectVehicle(getTrack(), position, ac.signal)
      .then((found) => {
        setVehicles(found.candidates);
        setLines(found.lines);
        setOffline(found.offline);
        setLiveUnavailable(Boolean(found.liveUnavailable));
        setManual(null);
        setSelectedId((prev) => (found.candidates.some((v) => v.id === prev) ? prev : found.candidates[0]?.id ?? null));
        setLoading(false);
        if (!requested.current) {
          const view = autoVehicleView(found);
          setOpen(view !== 'none');
          setSnap('bar'); // always the small collapsed bar; the user expands it
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
      setConfirmed(null); // "Nie jadę komunikacją": no vehicle to plan from
      setDelayVehicleId(null);
    },
    redetect: requestLinePopup,
  };
}
