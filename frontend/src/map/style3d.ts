import type { LayerSpecification, StyleSpecification } from 'maplibre-gl';
import type { MapLook } from './mapLook';
import type { StyleMode } from './palette';

/**
 * The 3D map (prototype): the same vector style, with the flat building layers replaced by extruded buildings
 * (`render_height` of the OpenMapTiles `building` layer) and a light that makes them look solid.
 */

/** Layers that draw buildings flat; the 3D layer takes their place. */
const FLAT_BUILDING_LAYERS = ['building', 'building-shadow', 'building-edge', 'building-highlight'];

/** Colours of the extruded buildings: lighter than the flat ones, so the walls read against the ground. */
export const BUILDING_3D: Record<MapLook, Record<StyleMode, { color: string; opacity: number }>> = {
  flat: {
    light: { color: '#EAD08C', opacity: 0.95 },
    dark: { color: '#5B4A32', opacity: 0.92 },
  },
  glass: {
    light: { color: '#FFC9A8', opacity: 0.82 },
    dark: { color: '#7C3F52', opacity: 0.86 },
  },
};

/** The camera of the 3D map: tilted, a little turned (so the streets are not in a flat grid). */
export const PITCH_3D = 55;
export const BEARING_3D = -17;

/** `style` with extruded buildings instead of flat ones. The input is not changed. */
export function with3dBuildings(style: StyleSpecification, look: MapLook, mode: StyleMode): StyleSpecification {
  const { color, opacity } = BUILDING_3D[look][mode];
  const layers = style.layers.filter((l) => !FLAT_BUILDING_LAYERS.includes(l.id));
  const extrusion = {
    id: 'building-3d',
    type: 'fill-extrusion',
    source: 'openmaptiles',
    'source-layer': 'building',
    minzoom: 14,
    paint: {
      'fill-extrusion-color': color,
      'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 8],
      'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
      'fill-extrusion-opacity': opacity,
      'fill-extrusion-vertical-gradient': true,
    },
  } as unknown as LayerSpecification;
  // before the first label, so the names stay readable on top of the buildings
  const firstLabel = layers.findIndex((l) => l.type === 'symbol');
  layers.splice(firstLabel === -1 ? layers.length : firstLabel, 0, extrusion);
  return {
    ...style,
    layers,
    light: { anchor: 'viewport', color: mode === 'dark' ? '#FFD9A8' : '#FFFFFF', intensity: mode === 'dark' ? 0.35 : 0.5, position: [1.4, 210, 45] },
  };
}
