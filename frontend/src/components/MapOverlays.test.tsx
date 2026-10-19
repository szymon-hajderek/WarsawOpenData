import { describe, expect, it } from 'vitest';
import { stationLabel, stationPlace } from './MapOverlays';

describe('overlay station as a place', () => {
  it('names a post with its number and gives the mapped position', () => {
    const s = { id: 'ztm:435102', kind: 'bus_post', name: 'Grójecka', code: '02', position: [52.1994, 20.966] as [number, number], entrances: [] };
    expect(stationLabel(s)).toBe('Grójecka 02');
    expect(stationPlace(s)).toEqual({ id: 'ztm:435102', label: 'Grójecka 02', sublabel: 'Przystanek', position: [52.1994, 20.966] });
  });

  it('does not add the Veturilo number to the name', () => {
    const s = { id: 'vet:203610', kind: 'veturilo', name: 'Koneser', code: '6419', position: [52.256, 21.046] as [number, number], entrances: [] };
    expect(stationPlace(s)).toMatchObject({ label: 'Koneser', sublabel: 'Stacja Veturilo' });
  });
});
