import { useCallback, useSyncExternalStore } from 'react';
import { createGlassStyle, createStyle } from './mapStyle';
import type { StyleMode } from './palette';

/** The two versions of the map: the flat Warsaw look and the "liquid glass" look. */
export type MapLook = 'flat' | 'glass';

const KEY = 'map-look';

export const createLookStyle = (look: MapLook, mode: StyleMode) =>
  look === 'glass' ? createGlassStyle(mode) : createStyle(mode);

function read(): MapLook {
  try {
    return localStorage.getItem(KEY) === 'glass' ? 'glass' : 'flat';
  } catch {
    return 'flat';
  }
}

// One value for the whole app: the Preferences page sets it, both maps follow.
let current: MapLook = read();
const listeners = new Set<() => void>();

/** Chooses the look, remembers it on the device and tells every map. */
export function setMapLook(next: MapLook): void {
  if (next === current) return;
  current = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    /* storage unavailable */
  }
  listeners.forEach((fn) => fn());
}

const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};

/** The chosen look (set in Preferences, "Widok") and a function that switches it. */
export function useMapLook(): [MapLook, () => void] {
  const look = useSyncExternalStore(subscribe, () => current, () => 'flat' as MapLook);
  const toggle = useCallback(() => setMapLook(current === 'glass' ? 'flat' : 'glass'), []);
  return [look, toggle];
}
