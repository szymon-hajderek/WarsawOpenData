import { describe, expect, it } from 'vitest';
import { stationsGeoJson } from './overlay3d';
import type { Station } from '../api/stations';

const st = (id: string, kind: string, lat = 52.2, lon = 21.0): Station => ({ id, kind, name: id, position: [lat, lon], entrances: [] });

describe('stationsGeoJson', () => {
  it('makes a point per station, in [lon, lat] order', () => {
    const fc = stationsGeoJson([st('ztm:1', 'bus_post', 52.21, 21.01)], new Map(), 'light');
    expect(fc.features).toHaveLength(1);
    expect(fc.features[0].geometry.coordinates).toEqual([21.01, 52.21]);
    expect(fc.features[0].properties).toMatchObject({ id: 'ztm:1', type: 'stop', big: false, count: '' });
  });

  it('metro and rail stops are bigger than bus and tram stops', () => {
    const [bus, metro, rail] = stationsGeoJson([st('a', 'bus_post'), st('b', 'metro_platform'), st('c', 'rail_station')], new Map(), 'dark').features;
    expect([bus.properties.big, metro.properties.big, rail.properties.big]).toEqual([false, true, true]);
  });

  it('Veturilo stations carry the bike count, grey when empty, and no count without live data', () => {
    const status = new Map([['vet:1', { bikes: 7, docks: 3 }], ['vet:2', { bikes: 0, docks: 10 }]]);
    const [a, b, c] = stationsGeoJson([st('vet:1', 'veturilo'), st('vet:2', 'veturilo'), st('vet:3', 'veturilo')], status, 'light').features;
    expect(a.properties).toMatchObject({ type: 'veturilo', count: '7' });
    expect(b.properties).toMatchObject({ count: '0', color: '#9E9E9E' });
    expect(c.properties.count).toBe('');
    expect(a.properties.color).not.toBe('#9E9E9E');
  });

  it('uses the colour of the mode of the stop', () => {
    const light = stationsGeoJson([st('a', 'tram_post')], new Map(), 'light').features[0].properties.color;
    const dark = stationsGeoJson([st('a', 'tram_post')], new Map(), 'dark').features[0].properties.color;
    expect(light).not.toBe(dark);
  });
});
