import { describe, expect, it } from 'vitest';
import { parseStation } from './stations';

describe('parseStation', () => {
  it('reads the mapped position and the entrances of a station', () => {
    const s = parseStation({
      id: 'ztm:7014M:P1',
      kind: 'metro_platform',
      name: 'Politechnika',
      position: { lat: 52.2185, lon: 21.0158 },
      entrances: [{ gtfs_id: 'e1', lat: 52.219, lon: 21.0165, osm_id: 1 }, { bad: true }],
      gtfs: { lat: 0, lon: 0 },
    });
    expect(s).toEqual({
      id: 'ztm:7014M:P1',
      kind: 'metro_platform',
      name: 'Politechnika',
      position: [52.2185, 21.0158],
      entrances: [[52.219, 21.0165]],
    });
  });

  it('refuses a location without an id or a position', () => {
    expect(parseStation({ kind: 'bus_post', name: 'x', position: { lat: 1, lon: 2 } })).toBeNull();
    expect(parseStation({ id: 'a', kind: 'bus_post', name: 'x', position: { lat: 1 } })).toBeNull();
    expect(parseStation(null)).toBeNull();
  });
});
