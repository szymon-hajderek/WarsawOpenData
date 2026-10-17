import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { LOOK_ORDER, type MapLook } from './map/looks';

interface MapLookValue {
  look: MapLook;
  /** Switches to the next look. */
  toggle: () => void;
}

const MapLookContext = createContext<MapLookValue>({ look: 'lavender', toggle: () => {} });
const STORAGE_KEY = 'map-variant';

function initialLook(): MapLook {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    // Old values ("v1", "v2") and anything unknown fall back to the default look.
    return LOOK_ORDER.find((l) => l === saved) ?? 'lavender';
  } catch {
    return 'lavender';
  }
}

export function MapLookProvider({ children }: { children: ReactNode }) {
  const [look, setLook] = useState<MapLook>(initialLook);

  const toggle = useCallback(() => {
    setLook((prev) => {
      const next = LOOK_ORDER[(LOOK_ORDER.indexOf(prev) + 1) % LOOK_ORDER.length];
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  const value = useMemo(() => ({ look, toggle }), [look, toggle]);
  return <MapLookContext.Provider value={value}>{children}</MapLookContext.Provider>;
}

export const useMapLook = () => useContext(MapLookContext);
