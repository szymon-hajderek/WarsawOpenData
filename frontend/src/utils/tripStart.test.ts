import { describe, expect, it } from 'vitest';
import { countdownText, mustWait, secondsUntil, tripStartAt } from './tripStart';

const at = (hh: number, mm: number, ss = 0, day = 18) => new Date(2026, 9, day, hh, mm, ss);

describe('tripStartAt', () => {
  it('a later departure today waits, with the right countdown', () => {
    const now = at(14, 7);
    const start = tripStartAt('14:30', now);
    expect(start).toEqual(at(14, 30));
    expect(mustWait(start, now)).toBe(true);
    expect(countdownText(secondsUntil(start, now))).toBe('za 23 min');
  });

  it('starts by itself at the departure time', () => {
    const start = tripStartAt('14:30', at(14, 7));
    expect(mustWait(start, at(14, 29, 30))).toBe(false); // within the last minute
    expect(secondsUntil(start, at(14, 30))).toBe(0);
  });

  it('a departure now or in the past starts at once', () => {
    expect(mustWait(tripStartAt('14:07', at(14, 7)), at(14, 7))).toBe(false);
    expect(mustWait(tripStartAt('13:50', at(14, 7)), at(14, 7))).toBe(false);
  });

  it('uses the date the search was made for', () => {
    const now = at(22, 0);
    const start = tripStartAt('08:15', now, '2026-10-19T08:00');
    expect(start).toEqual(at(8, 15, 0, 19));
    expect(countdownText(secondsUntil(start, now))).toBe('za 10 h 15 min');
  });

  it('a search for now just before midnight: an early departure is tomorrow', () => {
    expect(tripStartAt('00:10', at(23, 55))).toEqual(at(0, 10, 0, 19));
  });

  it('a search for 23:50 on a picked date: a departure at 00:10 is the next day', () => {
    expect(tripStartAt('00:10', at(9, 0), '2026-10-20T23:50')).toEqual(at(0, 10, 0, 21));
  });

  it('a picked time that has already passed starts at once', () => {
    const now = at(14, 7);
    expect(mustWait(tripStartAt('13:00', now, '2026-10-18T12:55'), now)).toBe(false);
  });
});
