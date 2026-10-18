import { afterEach, describe, expect, it } from 'vitest';
import { loadOverlays, saveOverlays, visibleKinds } from './overlays';

describe('map overlays', () => {
  afterEach(() => localStorage.clear());

  it('are all off by default and survive a reload', () => {
    expect(loadOverlays()).toEqual([]);
    saveOverlays(['rail', 'veturilo']);
    expect(loadOverlays()).toEqual(['veturilo', 'rail']);
  });

  it('ignores a broken or unknown saved value', () => {
    localStorage.setItem('map-overlays', '{oops');
    expect(loadOverlays()).toEqual([]);
    localStorage.setItem('map-overlays', '["stops","boats"]');
    expect(loadOverlays()).toEqual(['stops']);
  });

  it('loads stops only when zoomed in enough', () => {
    expect([...visibleKinds(['veturilo', 'stops'], 13)]).toEqual(['veturilo']);
    expect([...visibleKinds(['veturilo', 'stops'], 14)].sort()).toEqual(['bus_post', 'tram_post', 'veturilo']);
    expect(visibleKinds(['rail'], 12).size).toBe(0);
  });
});
