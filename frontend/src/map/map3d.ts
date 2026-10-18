import { useCallback, useState } from 'react';

const KEY = 'map-3d';

/** Whether the 3D map prototype is on; remembered on the device. */
export function useMap3d(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState<boolean>(() => {
    try {
      return localStorage.getItem(KEY) === '1';
    } catch {
      return false;
    }
  });
  const set = useCallback((next: boolean) => {
    setOn(next);
    try {
      localStorage.setItem(KEY, next ? '1' : '0');
    } catch {
      /* storage unavailable */
    }
  }, []);
  return [on, set];
}
