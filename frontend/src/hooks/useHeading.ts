import { useEffect, useState } from 'react';
import { angleDiff, compassHeading, smoothAngle, type OrientationLike } from '../utils/heading';

/** Compass smoothing factor per event (events come ~60 per second). */
const SMOOTH = 0.15;
/** The shown heading changes only by this much (fewer re-renders, no trembling). */
const MIN_CHANGE_DEG = 3;
/** At most this often (ms). */
const MIN_INTERVAL_MS = 150;
/** No compass reading for this long = no compass (desktop, sensor stopped): use the movement. */
const STALE_MS = 2_000;

type PermissionApi = { requestPermission?: () => Promise<'granted' | 'denied'> };

const screenAngle = () =>
  (typeof screen !== 'undefined' && screen.orientation?.angle) ||
  (typeof window !== 'undefined' && Number((window as { orientation?: number }).orientation)) ||
  0;

/**
 * Heading of the user's arrow (degrees from north) or null when unknown.
 * The compass when the device has one (Android `deviceorientationabsolute`, iOS `webkitCompassHeading`,
 * asked for on the first tap on iOS), else `moveHeading` = the direction of the last 3 GPS fixes.
 */
export function useHeading(moveHeading: number | null): number | null {
  const [compass, setCompass] = useState<number | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof DeviceOrientationEvent === 'undefined') return;
    const absoluteEvent = 'ondeviceorientationabsolute' in window;
    const type = absoluteEvent ? 'deviceorientationabsolute' : 'deviceorientation';
    let smooth: number | null = null;
    let shown: number | null = null;
    let shownAt = 0;
    let lastReading = 0;

    const onEvent = (e: Event) => {
      const h = compassHeading(e as unknown as OrientationLike, screenAngle(), absoluteEvent);
      if (h == null) return;
      const now = Date.now();
      lastReading = now;
      smooth = smoothAngle(smooth, h, SMOOTH);
      if (shown != null && (Math.abs(angleDiff(shown, smooth)) < MIN_CHANGE_DEG || now - shownAt < MIN_INTERVAL_MS)) return;
      shown = smooth;
      shownAt = now;
      setCompass(Math.round(smooth));
    };
    // The sensor stopped (or never started): fall back to the movement.
    const stale = setInterval(() => {
      if (shown != null && Date.now() - lastReading > STALE_MS) {
        shown = null;
        smooth = null;
        setCompass(null);
      }
    }, 1_000);

    const listen = () => window.addEventListener(type, onEvent);
    // iOS 13+: the compass needs a permission asked from a user gesture; ask on the first tap.
    const api = DeviceOrientationEvent as unknown as PermissionApi;
    const ask = () => {
      api
        .requestPermission?.()
        .then((r) => r === 'granted' && listen())
        .catch(() => undefined);
    };
    if (typeof api.requestPermission === 'function') window.addEventListener('click', ask, { once: true });
    else listen();

    return () => {
      window.removeEventListener(type, onEvent);
      window.removeEventListener('click', ask);
      clearInterval(stale);
    };
  }, []);

  return compass ?? moveHeading;
}
