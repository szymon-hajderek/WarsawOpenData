import { describe, expect, it } from 'vitest';
import type { StyleSpecification } from 'maplibre-gl';
import { createGlassStyle, createStyle } from './mapStyle';
import { BUILDING_3D, with3dBuildings } from './style3d';

const ids = (s: StyleSpecification) => s.layers.map((l) => l.id);

describe('with3dBuildings', () => {
  it('replaces the flat buildings of the flat look with one extruded layer', () => {
    const flat = createStyle('light');
    expect(ids(flat)).toContain('building');
    const out = with3dBuildings(flat, 'flat', 'light');
    expect(ids(out)).not.toContain('building');
    expect(ids(out).filter((id) => id === 'building-3d')).toHaveLength(1);
  });

  it('also removes the glass shadows, edges and highlights', () => {
    const out = with3dBuildings(createGlassStyle('dark'), 'glass', 'dark');
    for (const id of ['building', 'building-shadow', 'building-edge', 'building-highlight']) expect(ids(out)).not.toContain(id);
    expect(ids(out)).toContain('building-3d');
  });

  it('puts the buildings under the labels, so the names stay readable', () => {
    const out = with3dBuildings(createStyle('light'), 'flat', 'light');
    const layers = out.layers;
    const at = layers.findIndex((l) => l.id === 'building-3d');
    const firstLabel = layers.findIndex((l) => l.type === 'symbol');
    expect(at).toBeGreaterThan(-1);
    expect(at).toBeLessThan(firstLabel);
  });

  it('extrudes by the height of the tile data and uses the colour of the look and mode', () => {
    const out = with3dBuildings(createStyle('dark'), 'flat', 'dark');
    const layer = out.layers.find((l) => l.id === 'building-3d') as unknown as { type: string; paint: Record<string, unknown> };
    expect(layer.type).toBe('fill-extrusion');
    expect(JSON.stringify(layer.paint['fill-extrusion-height'])).toContain('render_height');
    expect(layer.paint['fill-extrusion-color']).toBe(BUILDING_3D.flat.dark.color);
    expect(out.light).toBeDefined();
  });

  it('does not change the style it was given', () => {
    const flat = createStyle('light');
    const before = ids(flat).length;
    with3dBuildings(flat, 'flat', 'light');
    expect(ids(flat)).toHaveLength(before);
    expect(flat.light).toBeUndefined();
  });
});
