import { useCallback, useState } from 'react';
import { createGlassStyle, createStyle } from './mapStyle';
import type { StyleMode } from './palette';

/** The two versions of the map: the flat Warsaw look and the "liquid glass" look. */
export type MapLook = 'flat' | 'glass';

const KEY = 'map-look';

export const createLookStyle = (look: MapLook, mode: StyleMode) =>
  look === 'glass' ? createGlassStyle(mode) : createStyle(mode);

/** The chosen look, remembered on the device. */
export function useMapLook(): [MapLook, () => void] {
  const [look, setLook] = useState<MapLook>(() => {
    try {
      return localStorage.getItem(KEY) === 'glass' ? 'glass' : 'flat';
    } catch {
      return 'flat';
    }
  });
  const toggle = useCallback(
    () =>
      setLook((l) => {
        const next = l === 'glass' ? 'flat' : 'glass';
        try {
          localStorage.setItem(KEY, next);
        } catch {
          /* storage unavailable */
        }
        return next;
      }),
    [],
  );
  return [look, toggle];
}
