import { describe, expect, it } from 'vitest';
import { rideDuration, sampleRide, type Ride } from './ride';

const fix = (t: number, lat: number, leg = 0, vehicle: string | null = null) => ({
  t, lat: lat + 0.0001, lon: 21, trueLat: lat, trueLon: 21, leg, vehicle,
});

const ride: Ride = {
  ok: true, reason: '', start: 100, end: 120, plan: [],
  fixes: [fix(100, 52), fix(110, 52.001), fix(120, 52.002, 1, 'bus-1')],
  events: [{ t: 115, event: 'board', line: '10', vehicle: 'bus-1' }],
  detections: [{ t: 120, vehicle: 'bus-1', candidates: [] }],
};

describe('sampleRide', () => {
  it('measures the duration from the start to the last fix', () => {
    expect(rideDuration(ride)).toBe(20);
  });

  it('is at the first fix before the start', () => {
    expect(sampleRide(ride, -5)?.truth).toEqual([52, 21]);
  });

  it('interpolates between two fixes', () => {
    const s = sampleRide(ride, 5);
    expect(s?.truth[0]).toBeCloseTo(52.0005, 6);
    expect(s?.gps[0]).toBeCloseTo(52.0006, 6);
  });

  it('stays at the last fix after the end and has the detection while in the vehicle', () => {
    const s = sampleRide(ride, 99);
    expect(s?.truth[0]).toBe(52.002);
    expect(s?.vehicle).toBe('bus-1');
    expect(s?.detection?.vehicle).toBe('bus-1');
    expect(s?.event?.event).toBe('board');
  });

  it('has no detection while on foot', () => {
    expect(sampleRide(ride, 3)?.detection).toBeNull();
  });

  it('returns null without fixes', () => {
    expect(sampleRide({ ...ride, fixes: [] }, 0)).toBeNull();
  });
});
