import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

/** v1 = raster OSM tiles (original look), v2 = flat pastel vector map. */
export type MapVariant = 'v1' | 'v2';

interface MapVariantValue {
  variant: MapVariant;
  toggle: () => void;
}

const MapVariantContext = createContext<MapVariantValue>({ variant: 'v1', toggle: () => {} });
const STORAGE_KEY = 'map-variant';

function initialVariant(): MapVariant {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'v2' ? 'v2' : 'v1';
  } catch {
    return 'v1';
  }
}

export function MapVariantProvider({ children }: { children: ReactNode }) {
  const [variant, setVariant] = useState<MapVariant>(initialVariant);

  const toggle = useCallback(() => {
    setVariant((prev) => {
      const next = prev === 'v1' ? 'v2' : 'v1';
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  const value = useMemo(() => ({ variant, toggle }), [variant, toggle]);
  return <MapVariantContext.Provider value={value}>{children}</MapVariantContext.Provider>;
}

export const useMapVariant = () => useContext(MapVariantContext);
