import type { StationKind } from '../api/stations';

/** Map overlays the user can switch on in the right map bar ("Warstwy przystanków"). */
export type OverlayId = 'veturilo' | 'stops' | 'rail';

export interface OverlayDef {
  id: OverlayId;
  label: string;
  kinds: StationKind[];
  /** Below this zoom the overlay is not drawn (too many points). */
  minZoom: number;
}

export const OVERLAYS: OverlayDef[] = [
  { id: 'veturilo', label: 'Stacje Veturilo', kinds: ['veturilo'], minZoom: 13 },
  { id: 'stops', label: 'Autobusy i tramwaje', kinds: ['bus_post', 'tram_post'], minZoom: 14 },
  { id: 'rail', label: 'Metro i kolej', kinds: ['metro_platform', 'rail_platform', 'rail_station'], minZoom: 14 },
];

const KEY = 'map-overlays';

/** The switched-on overlays saved on the device (all off by default). */
export function loadOverlays(): OverlayId[] {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(raw) ? OVERLAYS.map((o) => o.id).filter((id) => raw.includes(id)) : [];
  } catch {
    return [];
  }
}

export function saveOverlays(ids: OverlayId[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    /* storage unavailable */
  }
}

/** The overlays to draw at this zoom. */
export const visibleOverlays = (ids: OverlayId[], zoom: number): OverlayDef[] =>
  OVERLAYS.filter((o) => ids.includes(o.id) && zoom >= o.minZoom);

/** Station kinds to fetch at this zoom (empty = nothing to load). */
export const visibleKinds = (ids: OverlayId[], zoom: number): Set<string> =>
  new Set(visibleOverlays(ids, zoom).flatMap((o) => o.kinds));
