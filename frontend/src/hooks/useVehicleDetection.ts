import { useCallback, useEffect, useState } from 'react';
import {
  BUS_POPUP_REQUEST_EVENT,
  detectVehicle,
  manualCandidate,
  requestLinePopup,
  type TrackPoint,
} from '../api/vehicle';
import type { VehicleSnap } from '../components/VehicleSheet';
import type { LatLng, VehicleCandidate } from '../types';

interface Input {
  position: LatLng | null;
  geoError: boolean;
  getTrack: () => TrackPoint[];
}

/**
 * State of the "which vehicle am I in?" window. Detects once after start (first location, or none
 * after a geolocation error), then only when asked through `requestLinePopup()`.
 */
export function useVehicleDetection({ position, geoError, getTrack }: Input) {
  const [vehicles, setVehicles] = useState<VehicleCandidate[]>([]);
  const [lines, setLines] = useState<string[]>([]);
  const [manual, setManual] = useState<VehicleCandidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [mock, setMock] = useState(false);
  const [snap, setSnap] = useState<VehicleSnap>('middle');
  const [dismissed, setDismissed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<VehicleCandidate | null>(null);
  const [run, setRun] = useState(0);

  useEffect(() => {
    if (position || geoError) setRun((n) => n || 1);
  }, [position, geoError]);

  useEffect(() => {
    const onRequest = () => {
      setRun((n) => n + 1);
      setDismissed(false);
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
        setMock(found.mock);
        setManual(null);
        setSelectedId((prev) => (found.candidates.some((v) => v.id === prev) ? prev : found.candidates[0]?.id ?? null));
        setLoading(false);
      })
      .catch((err) => {
        if (ac.signal.aborted) return;
        console.warn('Vehicle detection failed', err);
        setLoading(false);
      });
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]);

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
    setConfirmed(all.find((v) => v.id === selectedId) ?? null);
    setSnap('bar');
  }, [manual, vehicles, selectedId]);

  return {
    vehicles,
    lines,
    manual,
    loading,
    mock,
    snap,
    dismissed,
    selectedId,
    confirmed,
    setSnap,
    setSelectedId,
    selectManualLine,
    clearManual,
    confirm,
    dismiss: () => setDismissed(true),
    redetect: requestLinePopup,
  };
}
