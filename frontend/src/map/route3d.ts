import type { PaletteMode } from '@mui/material';
import type { Feature, FeatureCollection, LineString } from 'geojson';
import { modeColor } from '../modes';
import { PALETTE } from './palette';
import { legLines } from '../utils/legStyle';
import type { RouteOption } from '../types';

/** What a line of the route looks like on the 3D map. */
export interface RouteLineProps {
  color: string;
  /** `solid`, `dashed` (pushed bike, approximate path), `dotted` (walking) or `access` (steps, elevator). */
  style: 'solid' | 'dashed' | 'dotted' | 'access';
  /** Rides get a light casing under the line, walking does not. */
  casing: boolean;
}

/** The lines of a route as GeoJSON (`[lon, lat]`), one feature per line of a leg, for the 3D map. */
export function routeGeoJson(route: RouteOption, palette: PaletteMode): FeatureCollection<LineString, RouteLineProps> {
  const features: Feature<LineString, RouteLineProps>[] = [];
  for (const leg of route.legs) {
    const walk = leg.mode === 'walk';
    const color = walk ? PALETTE[palette].accent : modeColor(leg.mode, palette);
    for (const line of legLines(leg)) {
      if (line.path.length < 2) continue;
      features.push({
        type: 'Feature',
        properties: { color: line.style === 'access' ? PALETTE[palette].accent : color, style: line.style, casing: !walk && line.style !== 'access' },
        geometry: { type: 'LineString', coordinates: line.path.map(([lat, lon]) => [lon, lat]) },
      });
    }
  }
  return { type: 'FeatureCollection', features };
}
