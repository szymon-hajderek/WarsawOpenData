import { useEffect, useState } from 'react';
import { angleDiff, compassHeading, smoothAngle, type OrientationLike } from '../utils/heading';

/** Compass smoothing time constant (ms): independent of the event rate (60 Hz or a few per second). */
const SMOOTH_TAU_MS = 200;
/** The shown heading changes only by this much (fewer re-renders, no trembling). */
const MIN_CHANGE_DEG = 3;
/** At most this often (ms); the last reading is still shown after a pause. */
const MIN_INTERVAL_MS = 150;

type PermissionApi = { requestPermission?: () => Promise<'granted' | 'denied'> };

const screenAngle = () =>
  (typeof screen !== 'undefined' && screen.orientation?.angle) ||
  (typeof window !== 'undefined' && Number((window as { orientation?: number }).orientation)) ||
  0;

/**
 * Heading of the user's arrow (degrees from north) or null when unknown.
 * The compass once it gave one reading (Android `deviceorientationabsolute`, iOS `webkitCompassHeading`,
 * asked for on the first tap on iOS); it stays while the phone lies still (no events then). Without a compass:
 * `moveHeading` = the direction of the last 3 GPS fixes (null while standing).
 */
export function useHeading(moveHeading: number | null): number | null {
  const [compass, setCompass] = useState<number | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof DeviceOrientationEvent === 'undefined') return;
    const absoluteEvent = 'ondeviceorientationabsolute' in window;
    const type = absoluteEvent ? 'deviceorientationabsolute' : 'deviceorientation';
    let smooth: number | null = null;
    let smoothAt = 0;
    let shown: number | null = null;
    let shownAt = 0;
    let flush: ReturnType<typeof setTimeout> | undefined;

    const show = () => {
      flush = undefined;
      if (smooth == null || (shown != null && Math.abs(angleDiff(shown, smooth)) < MIN_CHANGE_DEG)) return;
      shown = smooth;
      shownAt = Date.now();
      setCompass(Math.round(smooth));
    };
    const onEvent = (e: Event) => {
      const h = compassHeading(e as unknown as OrientationLike, screenAngle(), absoluteEvent);
      if (h == null) return;
      const now = Date.now();
      smooth = smoothAngle(smooth, h, 1 - Math.exp(-(now - smoothAt) / SMOOTH_TAU_MS));
      smoothAt = now;
      if (now - shownAt >= MIN_INTERVAL_MS) show();
      else flush ??= setTimeout(show, MIN_INTERVAL_MS - (now - shownAt));
    };

    const listen = () => window.addEventListener(type, onEvent);
    // iOS 13+: the compass needs a permission asked from a user gesture; ask on the first tap
    // (capture phase, so a control that stops propagation still counts).
    const api = DeviceOrientationEvent as unknown as PermissionApi;
    const gestures = ['click', 'touchend'] as const;
    const ask = () => {
      gestures.forEach((g) => window.removeEventListener(g, ask, true));
      api
        .requestPermission?.()
        .then((r) => r === 'granted' && listen())
        .catch(() => undefined);
    };
    if (typeof api.requestPermission === 'function') gestures.forEach((g) => window.addEventListener(g, ask, true));
    else listen();

    return () => {
      window.removeEventListener(type, onEvent);
      gestures.forEach((g) => window.removeEventListener(g, ask, true));
      clearTimeout(flush);
    };
  }, []);

  return compass ?? moveHeading;
}
