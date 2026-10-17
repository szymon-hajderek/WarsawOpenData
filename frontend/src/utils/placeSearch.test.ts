import { describe, expect, it } from 'vitest';
import { fold, matchScore, searchRows, type PlaceRow } from './placeSearch';

describe('placeSearch', () => {
  it('folds case and Polish accents', () => {
    expect(fold('  Łódź-Kaliska ')).toBe('lodz kaliska');
  });

  it('ranks the whole name, the start, word starts and the inside in this order', () => {
    expect(matchScore('Centrum', 'Centrum')).toBe(0);
    expect(matchScore('cent', 'Centrum')).toBe(1);
    expect(matchScore('politechn', 'Metro Politechnika')).toBe(2);
    expect(matchScore('echni', 'Metro Politechnika')).toBe(3);
    expect(matchScore('xyz', 'Metro Politechnika')).toBeNull();
  });

  const rows: PlaceRow[] = [
    ['Stacja Centrum', 52.2, 21.0, 0],
    ['Centrum Nauki', 52.2, 21.0, 1],
    ['Centrum', 52.2, 21.0, 0],
  ];

  it('puts better matches first and labels the kind', () => {
    const found = searchRows(rows, 'centrum');
    expect(found.map((p) => p.label)).toEqual(['Centrum', 'Centrum Nauki', 'Stacja Centrum']);
    expect(found[1].sublabel).toBe('Stacja Veturilo');
    expect(found[0].sublabel).toBe('Przystanek');
  });

  it('orders equal matches by distance from the user', () => {
    const near: PlaceRow[] = [['Wilanowska', 52.17, 21.03, 0], ['Wilanowska', 52.23, 21.0, 0]];
    expect(searchRows(near, 'wilan', 4, [52.231, 21.0])[0].position[0]).toBe(52.23);
  });
});
