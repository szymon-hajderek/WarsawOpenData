import { describe, expect, it } from 'vitest';
import type { Place } from '../types';
import { MAX_PLACES, decayed, recordPlaces, topPlaces } from './frequentPlaces';

const MIN = 60 * 1000;
const DAY = 24 * 3600 * 1000;
const place = (id: string, label = id): Place => ({ id, label, position: [52.23, 21.01] });
const here: Place = { ...place('me', 'Moja lokalizacja'), isCurrentLocation: true };

describe('frequent places', () => {
  it('suggests a place from two searches', () => {
    let list = recordPlaces([], [place('a')], 0);
    expect(topPlaces(list, 0)).toEqual([]);
    list = recordPlaces(list, [place('a')], 11 * MIN);
    expect(topPlaces(list, 11 * MIN).map((p) => p.id)).toEqual(['a']);
  });

  it('counts the same place once per 10 minutes', () => {
    let list = recordPlaces([], [place('a')], 0);
    list = recordPlaces(list, [place('a')], 5 * MIN);
    expect(list[0].score).toBe(1);
  });

  it('never stores the current location', () => {
    expect(recordPlaces([], [here, place('a')], 0).map((p) => p.id)).toEqual(['a']);
  });

  it('halves the points after 30 days', () => {
    const [p] = recordPlaces([], [place('a')], 0);
    expect(decayed(p, 30 * DAY)).toBeCloseTo(0.5);
  });

  it('ranks recent searches above old ones with the same count', () => {
    let list: ReturnType<typeof recordPlaces> = [];
    for (const t of [0, 20 * MIN]) list = recordPlaces(list, [place('old')], t);
    for (const t of [40 * DAY, 40 * DAY + 20 * MIN]) list = recordPlaces(list, [place('new')], t);
    expect(topPlaces(list, 40 * DAY + 20 * MIN).map((p) => p.id)).toEqual(['new']);
  });

  it('keeps at most MAX_PLACES', () => {
    const many = Array.from({ length: MAX_PLACES + 5 }, (_, i) => place(`p${i}`));
    expect(recordPlaces([], many, 0)).toHaveLength(MAX_PLACES);
  });

  it('filters by the typed text', () => {
    let list = recordPlaces([], [place('a', 'Dworzec Centralny'), place('b', 'Politechnika')], 0);
    list = recordPlaces(list, [place('a', 'Dworzec Centralny'), place('b', 'Politechnika')], 11 * MIN);
    expect(topPlaces(list, 11 * MIN, 3, 'poli').map((p) => p.id)).toEqual(['b']);
    expect(topPlaces(list, 11 * MIN, 3, 'xyz')).toEqual([]);
  });
});
