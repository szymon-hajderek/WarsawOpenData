import { useCallback, useState } from 'react';
import { loadOverlays, saveOverlays, type OverlayId } from '../map/overlays';

/** The switched-on stop layers ("Warstwy przystanków"), remembered on the device; shared by the 2D and the 3D map. */
export function useOverlayIds(): [OverlayId[], (id: OverlayId) => void] {
  const [ids, setIds] = useState<OverlayId[]>(loadOverlays);
  const toggle = useCallback((id: OverlayId) => {
    setIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      saveOverlays(next);
      return next;
    });
  }, []);
  return [ids, toggle];
}
