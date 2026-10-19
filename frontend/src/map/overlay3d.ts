import type { PaletteMode } from '@mui/material';
import type { Feature, FeatureCollection, Point } from 'geojson';
import type { Station } from '../api/stations';
import type { DockStatus } from '../api/veturilo';
import { modeColor } from '../modes';
import type { TransportMode } from '../types';

const KIND_MODE: Record<string, TransportMode> = {
  bus_post: 'bus',
  tram_post: 'tram',
  metro_platform: 'metro',
  rail_platform: 'rail',
  rail_station: 'rail',
  veturilo: 'veturilo',
};

export interface StationProps {
  id: string;
  color: string;
  /** `veturilo` (a pill with the bike count) or `stop` (a dot). */
  type: 'veturilo' | 'stop';
  /** Bike count of a Veturilo station; empty text without live data. */
  count: string;
  /** Stops of metro and rail are a little bigger. */
  big: boolean;
}

/** The stations of the stop layers as GeoJSON points (`[lon, lat]`) for the 3D map. */
export function stationsGeoJson(
  stations: Station[],
  status: ReadonlyMap<string, DockStatus>,
  palette: PaletteMode,
): FeatureCollection<Point, StationProps> {
  const features: Feature<Point, StationProps>[] = stations.map((s) => {
    const dock = status.get(s.id);
    const vet = s.kind === 'veturilo';
    return {
      type: 'Feature',
      properties: {
        id: s.id,
        type: vet ? 'veturilo' : 'stop',
        color: vet && dock?.bikes === 0 ? '#9E9E9E' : modeColor(KIND_MODE[s.kind] ?? 'bus', palette),
        count: vet && dock ? String(dock.bikes) : '',
        big: s.kind !== 'bus_post' && s.kind !== 'tram_post' && !vet,
      },
      geometry: { type: 'Point', coordinates: [s.position[1], s.position[0]] },
    };
  });
  return { type: 'FeatureCollection', features };
}
