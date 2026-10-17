import type { LayerSpecification, StyleSpecification } from 'maplibre-gl';

import { GLASS, PALETTE, type MapColors, type StyleMode } from './palette';

/**
 * Flat map style (OpenMapTiles schema, vector tiles from OpenFreeMap).
 * Colours come from `src/map/palette.ts`; the layers below only reference them.
 */
// Layer fragments use MapLibre expressions, which are loosely typed arrays.
type Layer = Record<string, unknown>;

const NAME = ['coalesce', ['get', 'name:pl'], ['get', 'name']];
const FONT_REGULAR = ['Noto Sans Regular'];
const FONT_BOLD = ['Noto Sans Bold'];

const zoomWidth = (...stops: number[]) => ['interpolate', ['exponential', 1.4], ['zoom'], ...stops];
const classIn = (...classes: string[]) => ['match', ['get', 'class'], classes, true, false];

export function createStyle(mode: StyleMode): StyleSpecification {
  const p = PALETTE[mode].map;

  const road = (id: string, classes: string[], minzoom: number, width: number[], color: string): Layer => ({
    id,
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'transportation',
    minzoom,
    filter: classIn(...classes),
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': color, 'line-width': zoomWidth(...width) },
  });

  const layers: Layer[] = [
    { id: 'background', type: 'background', paint: { 'background-color': p.background } },

    // Green areas and water
    {
      id: 'wood',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landcover',
      filter: classIn('wood', 'grass'),
      paint: { 'fill-color': p.wood },
    },
    {
      id: 'park',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'park',
      paint: { 'fill-color': p.park },
    },
    {
      id: 'green-landuse',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landuse',
      filter: classIn('cemetery', 'playground', 'pitch', 'stadium'),
      paint: { 'fill-color': p.park, 'fill-opacity': 0.8 },
    },
    {
      id: 'water',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'fill-color': p.water },
    },
    {
      id: 'waterway',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'waterway',
      paint: { 'line-color': p.water, 'line-width': zoomWidth(8, 0.6, 16, 4) },
    },

    // Buildings: very light blocks that appear when zoomed in
    {
      id: 'building',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'building',
      minzoom: 14,
      paint: {
        'fill-color': p.building,
        'fill-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, 0.9],
      },
    },

    // Roads: casing first, then the inner line
    road('path', ['path', 'pedestrian', 'track'], 15, [15, 0.6, 19, 2.5], p.path),
    road('minor-casing', ['minor', 'service'], 13, [13, 1.2, 16, 7, 19, 26], p.roadMinorCasing),
    road('tertiary-casing', ['tertiary'], 11, [11, 1.4, 16, 9, 19, 30], p.roadMajorCasing),
    road('major-casing', ['secondary', 'primary', 'trunk', 'motorway'], 8, [8, 1.6, 16, 11, 19, 34], p.roadMajorCasing),
    road('minor', ['minor', 'service'], 13, [13, 0.6, 16, 5, 19, 22], p.roadMinor),
    road('tertiary', ['tertiary'], 11, [11, 0.7, 16, 7, 19, 26], p.roadMajor),
    road('major', ['secondary', 'primary', 'trunk', 'motorway'], 8, [8, 0.8, 16, 9, 19, 30], p.roadMajor),

    // Rail and tram lines: useful context for a transit app
    {
      id: 'rail',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'transportation',
      minzoom: 12,
      filter: classIn('rail', 'transit'),
      paint: {
        'line-color': p.rail,
        'line-width': zoomWidth(12, 0.6, 18, 2.2),
        'line-dasharray': [3, 2],
      },
    },

    ...labelLayers(p),
  ];

  return styleSpec(layers);
}

/**
 * "Liquid glass" look: a warm, luminous map. Roads are glowing strands, buildings are small glass tiles with a bright edge
 * and a soft red shadow, water has a light shore. Same tiles and labels as the flat look.
 */
export function createGlassStyle(mode: StyleMode): StyleSpecification {
  const g = GLASS[mode];

  const road = (id: string, classes: string[], minzoom: number, width: number[], color: string): Layer => ({
    id,
    type: 'line',
    source: 'openmaptiles',
    'source-layer': 'transportation',
    minzoom,
    filter: classIn(...classes),
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': color, 'line-width': zoomWidth(...width) },
  });
  /** The same road with a blur: a glow that spreads wider than the road itself. */
  const glow = (id: string, classes: string[], minzoom: number, width: number[], color: string): Layer => {
    const layer = road(id, classes, minzoom, width, color);
    (layer.paint as Layer)['line-blur'] = 9;
    return layer;
  };
  const MAJOR = ['secondary', 'primary', 'trunk', 'motorway'];

  const layers: Layer[] = [
    { id: 'background', type: 'background', paint: { 'background-color': g.background } },
    { id: 'wood', type: 'fill', source: 'openmaptiles', 'source-layer': 'landcover', filter: classIn('wood', 'grass'), paint: { 'fill-color': g.wood } },
    { id: 'park', type: 'fill', source: 'openmaptiles', 'source-layer': 'park', paint: { 'fill-color': g.park } },
    {
      id: 'green-landuse',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'landuse',
      filter: classIn('cemetery', 'playground', 'pitch', 'stadium'),
      paint: { 'fill-color': g.park, 'fill-opacity': 0.8 },
    },

    // Water: glass with a blurred light shore and a thin sharp edge
    { id: 'water', type: 'fill', source: 'openmaptiles', 'source-layer': 'water', paint: { 'fill-color': g.water } },
    {
      id: 'water-shore-glow',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'line-color': g.edge, 'line-opacity': 0.9, 'line-width': zoomWidth(8, 5, 16, 20), 'line-blur': 7 },
    },
    {
      id: 'water-shore',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'water',
      paint: { 'line-color': g.edge, 'line-width': zoomWidth(8, 0.5, 16, 1.4) },
    },
    {
      id: 'waterway',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'waterway',
      paint: { 'line-color': g.water, 'line-width': zoomWidth(8, 0.8, 16, 5) },
    },

    // Roads: glow, casing, then the bright core
    road('path', ['path', 'pedestrian', 'track'], 15, [15, 0.8, 19, 3], g.path),
    glow('minor-glow', ['minor', 'service'], 13, [13, 3, 16, 18, 19, 56], g.roadGlow),
    glow('major-glow', ['tertiary', ...MAJOR], 9, [9, 4, 16, 24, 19, 70], g.roadMajorGlow),
    road('minor-casing', ['minor', 'service'], 13, [13, 1.2, 16, 7, 19, 26], g.roadMinorCasing),
    road('major-casing', ['tertiary', ...MAJOR], 9, [9, 1.6, 16, 11, 19, 34], g.roadMajorCasing),
    road('minor', ['minor', 'service'], 13, [13, 0.6, 16, 5, 19, 22], g.roadMinor),
    road('major', ['tertiary', ...MAJOR], 9, [9, 0.9, 16, 9, 19, 30], g.roadMajor),

    // Buildings: a soft shadow, the glass tile, a bright edge
    {
      id: 'building-shadow',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'building',
      minzoom: 14,
      paint: {
        'fill-color': g.buildingShadow,
        'fill-translate': [3, 4],
        'fill-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, 1],
      },
    },
    {
      id: 'building',
      type: 'fill',
      source: 'openmaptiles',
      'source-layer': 'building',
      minzoom: 14,
      paint: { 'fill-color': g.building, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0, 16, 1] },
    },
    {
      id: 'building-edge',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'building',
      minzoom: 15,
      paint: {
        'line-color': g.edge,
        'line-width': ['interpolate', ['linear'], ['zoom'], 15, 0.4, 19, 1.4],
        'line-opacity': ['interpolate', ['linear'], ['zoom'], 15, 0, 16.5, 1],
      },
    },
    {
      id: 'building-highlight',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'building',
      minzoom: 16,
      paint: { 'line-color': '#FFFFFF', 'line-width': 0.8, 'line-translate': [-1, -1], 'line-opacity': 0.55, 'line-blur': 0.6 },
    },
    {
      id: 'rail',
      type: 'line',
      source: 'openmaptiles',
      'source-layer': 'transportation',
      minzoom: 12,
      filter: classIn('rail', 'transit'),
      paint: { 'line-color': g.rail, 'line-width': zoomWidth(12, 1, 18, 3), 'line-dasharray': [3, 2] },
    },
    ...labelLayers(g),
  ];

  return styleSpec(layers);
}

function styleSpec(layers: Layer[]): StyleSpecification {
  return {
    version: 8,
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    sources: { openmaptiles: { type: 'vector', url: 'https://tiles.openfreemap.org/planet' } },
    layers: layers as unknown as LayerSpecification[],
  };
}

/** Labels, the same in every look; only the colours differ. Bigger places first, smaller streets and POIs only when zoomed in. */
function labelLayers(p: MapColors): Layer[] {
  const label = (id: string, extra: Layer): Layer => {
    const { paint, layout, ...rest } = extra;
    return {
      type: 'symbol',
      id,
      ...rest,
      paint: {
        'text-color': p.label,
        'text-halo-color': p.labelHalo,
        'text-halo-width': 1.5,
        ...(paint as Layer | undefined),
      },
      layout: { 'text-font': FONT_REGULAR, 'text-field': NAME, ...(layout as Layer | undefined) },
    };
  };

  return [
    // Labels. Bigger places first, smaller streets and POIs only when zoomed in.
    label('water-label', {
      'source-layer': 'water_name',
      source: 'openmaptiles',
      minzoom: 10,
      paint: { 'text-color': p.waterLabel },
      layout: { 'text-size': 12, 'text-font': ['Noto Sans Italic'] },
    }),
    label('place-city', {
      source: 'openmaptiles',
      'source-layer': 'place',
      filter: ['==', ['get', 'class'], 'city'],
      maxzoom: 13,
      layout: { 'text-font': FONT_BOLD, 'text-size': ['interpolate', ['linear'], ['zoom'], 5, 12, 12, 22] },
    }),
    label('place-town', {
      source: 'openmaptiles',
      'source-layer': 'place',
      filter: classIn('town', 'village'),
      maxzoom: 15,
      layout: { 'text-size': ['interpolate', ['linear'], ['zoom'], 8, 11, 14, 15] },
    }),
    label('place-suburb', {
      source: 'openmaptiles',
      'source-layer': 'place',
      filter: classIn('suburb', 'quarter'),
      minzoom: 11,
      maxzoom: 16,
      paint: { 'text-color': p.labelSoft },
      layout: {
        'text-font': FONT_BOLD,
        'text-transform': 'uppercase',
        'text-letter-spacing': 0.1,
        'text-size': ['interpolate', ['linear'], ['zoom'], 11, 10, 15, 13],
      },
    }),
    label('place-neighbourhood', {
      source: 'openmaptiles',
      'source-layer': 'place',
      filter: classIn('neighbourhood', 'hamlet', 'isolated_dwelling'),
      minzoom: 14,
      paint: { 'text-color': p.labelSoft },
      layout: { 'text-size': 11 },
    }),
    label('road-name-major', {
      source: 'openmaptiles',
      'source-layer': 'transportation_name',
      filter: classIn('motorway', 'trunk', 'primary', 'secondary', 'tertiary'),
      minzoom: 13,
      layout: {
        'symbol-placement': 'line',
        'text-size': ['interpolate', ['linear'], ['zoom'], 13, 10, 18, 14],
      },
    }),
    label('road-name-minor', {
      source: 'openmaptiles',
      'source-layer': 'transportation_name',
      filter: classIn('minor', 'service'),
      minzoom: 16,
      paint: { 'text-color': p.labelSoft },
      layout: { 'symbol-placement': 'line', 'text-size': 11 },
    }),
    label('road-name-path', {
      source: 'openmaptiles',
      'source-layer': 'transportation_name',
      filter: classIn('path', 'pedestrian', 'track'),
      minzoom: 17,
      paint: { 'text-color': p.labelSoft },
      layout: { 'symbol-placement': 'line', 'text-size': 10 },
    }),
    label('poi', {
      source: 'openmaptiles',
      'source-layer': 'poi',
      minzoom: 16.5,
      filter: ['has', 'name'],
      paint: { 'text-color': p.labelSoft },
      layout: { 'text-size': 11, 'text-anchor': 'top', 'text-offset': [0, 0.4], 'text-max-width': 7 },
    }),
    label('housenumber', {
      source: 'openmaptiles',
      'source-layer': 'housenumber',
      minzoom: 18,
      paint: { 'text-color': p.labelSoft },
      layout: { 'text-field': ['get', 'housenumber'], 'text-size': 10 },
    }),
  ];
}

export const MAP_ATTRIBUTION =
  '&copy; <a href="https://openfreemap.org">OpenFreeMap</a> ' +
  '&copy; <a href="https://www.openmaptiles.org/">OpenMapTiles</a> ' +
  'Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
