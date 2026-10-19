import { useCallback, useEffect, useRef, useState } from 'react';
import { haversine } from '../utils/geo';
import { addFix, movementHeading, type Fix } from '../utils/heading';
import type { LatLng } from '../types';
import type { TrackPoint } from '../api/vehicle';

const SAMPLE_MS = 10_000;
const MAX_POINTS = 3;
/** The shown position changes only after the user moved this far (fewer re-renders). */
const MOVE_M = 15;

/** Browsers give the location only to secure pages (HTTPS or localhost). */
export const isInsecurePage = () => typeof window !== 'undefined' && window.isSecureContext === false;

/** Text of the snackbar shown when the location could not be read. */
export const geoErrorText = (insecure = isInsecurePage()) =>
  insecure
    ? 'Lokalizacja działa tylko na stronie z HTTPS. Uruchom npm run dev:https albo wpisz punkt startowy ręcznie.'
    : 'Nie udało się ustalić lokalizacji. Wpisz punkt startowy ręcznie.';

/**
 * The user's location: one `watchPosition` stream, cleaned up when the component unmounts.
 * It also keeps the last 1-3 positions (one every 10 s, memory only) for the vehicle detection,
 * and the direction of movement from the last 3 fixes that are farther apart than the GPS error (`moveHeading`).
 */
export function useLocationTrack() {
  const [position, setPosition] = useState<LatLng | null>(null);
  const [geoError, setGeoError] = useState(false);
  const latest = useRef<TrackPoint | null>(null);
  const track = useRef<TrackPoint[]>([]);
  const fixes = useRef<Fix[]>([]);
  const [moveHeading, setMoveHeading] = useState<number | null>(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setGeoError(true);
      return;
    }
    const updateHeading = () => {
      const h = movementHeading(fixes.current, Date.now());
      setMoveHeading(h == null ? null : Math.round(h));
    };
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        latest.current = { lat: latitude, lon: longitude, time_ms: Date.now() };
        if (track.current.length === 0) track.current.push(latest.current);
        fixes.current = addFix(fixes.current, {
          pos: [latitude, longitude],
          accuracy: accuracy ?? 0,
          time: Date.now(),
        });
        updateHeading();
        setPosition((prev) =>
          prev && haversine(prev, [latitude, longitude]) < MOVE_M ? prev : [latitude, longitude],
        );
      },
      () => setGeoError(true),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
    const timer = setInterval(() => {
      updateHeading(); // the user stopped: back to the dot
      if (!latest.current) return;
      track.current.push({ ...latest.current, time_ms: Date.now() });
      track.current.splice(0, track.current.length - MAX_POINTS);
    }, SAMPLE_MS);
    return () => {
      navigator.geolocation.clearWatch(watchId);
      clearInterval(timer);
    };
  }, []);

  /** Asks for the position once more (the "my location" button). */
  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      setGeoError(true);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setPosition([pos.coords.latitude, pos.coords.longitude]),
      () => setGeoError(true),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }, []);

  /** The last 1-3 positions; empty when there is no fix yet. */
  const getTrack = useCallback((): TrackPoint[] => [...track.current], []);

  return { position, moveHeading, geoError, clearGeoError: () => setGeoError(false), locate, getTrack };
}
