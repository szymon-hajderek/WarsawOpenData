import { describe, expect, it } from 'vitest';
import { bikeSplit, legLines, legNotes, legStyle, segmentStyle } from './legStyle';
import type { LatLng, RouteLeg } from '../types';

const leg = (over: Partial<RouteLeg>): RouteLeg => ({
  mode: 'bike',
  from: 'a',
  to: 'b',
  durationMin: 10,
  distanceM: 1000,
  path: [[52.2, 21.0], [52.201, 21.001], [52.21, 21.01]],
  ...over,
});
const A: LatLng = [52.2, 21.0];
const B: LatLng = [52.201, 21.001];
const C: LatLng = [52.21, 21.01];
const bike = leg({
  segments: [
    { kind: 'push', path: [A, B], lengthM: 120 },
    { kind: 'ride', path: [B, C], lengthM: 1340 },
  ],
});

describe('segmentStyle', () => {
  it('ridden solid, pushed dashed, walked dotted, steps / elevator / metro access their own style', () => {
    expect(segmentStyle('ride')).toBe('solid');
    expect(segmentStyle('push')).toBe('dashed');
    expect(segmentStyle('walk')).toBe('dotted');
    expect(segmentStyle('steps')).toBe('access');
    expect(segmentStyle('elevator')).toBe('access');
    expect(segmentStyle('metro_access')).toBe('access');
  });
});

describe('legStyle', () => {
  it('a transit leg with an approximate path is dashed; without the field it stays solid', () => {
    expect(legStyle(leg({ mode: 'bus', approximatePath: true }))).toBe('dashed');
    expect(legStyle(leg({ mode: 'bus' }))).toBe('solid');
    expect(legStyle(leg({ mode: 'tram', approximatePath: false }))).toBe('solid');
    expect(legStyle(leg({ mode: 'walk' }))).toBe('dotted');
  });
});

describe('legLines', () => {
  it('a leg without segments is one line along the joined path', () => {
    const joined: LatLng[] = [[52.1999, 21.0], ...leg({}).path];
    expect(legLines(leg({}), joined)).toEqual([{ path: joined, style: 'solid' }]);
    expect(legLines(leg({ mode: 'rail', approximatePath: true }))[0].style).toBe('dashed');
  });

  it('a bike leg: one line per segment, pushed dashed and ridden solid', () => {
    expect(legLines(bike)).toEqual([
      { path: [A, B], style: 'dashed' },
      { path: [B, C], style: 'solid' },
    ]);
  });

  it('keeps the connectors to the stop markers on the first and the last segment', () => {
    const stopA: LatLng = [52.1998, 20.9998];
    const stopC: LatLng = [52.2102, 21.0102];
    const lines = legLines(bike, [stopA, A, B, C, stopC]);
    expect(lines[0].path).toEqual([stopA, A, B]);
    expect(lines[1].path).toEqual([B, C, stopC]);
    // the leg itself is not changed
    expect(bike.segments![0].path).toEqual([A, B]);
  });
});

describe('bikeSplit / legNotes', () => {
  it('sums ridden and pushed metres of a bike leg', () => {
    expect(bikeSplit(bike)).toEqual({ rideM: 1340, pushM: 120 });
    expect(legNotes(bike)).toEqual(['jazda 1,3 km, prowadzenie 120 m']);
  });

  it('says nothing for a bike leg without segments or a walking leg', () => {
    expect(bikeSplit(leg({}))).toBeNull();
    expect(bikeSplit(leg({ mode: 'walk', segments: [{ kind: 'walk', path: [A, B], lengthM: 100 }] }))).toBeNull();
    expect(legNotes(leg({}))).toEqual([]);
  });

  it('notes an approximate transit path', () => {
    expect(legNotes(leg({ mode: 'bus', approximatePath: true }))).toEqual(['przebieg orientacyjny']);
  });
});
