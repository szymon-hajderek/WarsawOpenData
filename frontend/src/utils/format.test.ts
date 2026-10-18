import { describe, expect, it } from 'vitest';
import { formatTotalWait, formatWait, waitMinutes } from './format';

describe('wait texts', () => {
  it('rounds to whole minutes from one minute on', () => {
    expect(waitMinutes(60)).toBe(1);
    expect(waitMinutes(149)).toBe(2);
    expect(waitMinutes(150)).toBe(3);
    expect(formatWait(240)).toBe('czekasz 4 min');
    expect(formatTotalWait(371)).toBe('w tym czekanie 6 min');
  });

  it('says nothing below a minute or without a wait', () => {
    expect(waitMinutes(59.9)).toBe(0);
    expect(formatWait(0)).toBeNull();
    expect(formatWait(undefined)).toBeNull();
    expect(formatTotalWait(30)).toBeNull();
    expect(formatTotalWait(undefined)).toBeNull();
  });
});
