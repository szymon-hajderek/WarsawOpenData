import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { geoErrorText, useLocationTrack } from './useLocationTrack';

type Success = (pos: { coords: { latitude: number; longitude: number } }) => void;

describe('useLocationTrack', () => {
  const clearWatch = vi.fn();
  let success: Success = () => {};

  beforeEach(() => {
    vi.useFakeTimers();
    clearWatch.mockClear();
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        watchPosition: vi.fn((ok: Success) => {
          success = ok;
          return 7;
        }),
        getCurrentPosition: vi.fn(),
        clearWatch,
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps the last 3 positions, one every 10 s', () => {
    const { result } = renderHook(() => useLocationTrack());
    act(() => success({ coords: { latitude: 52.2, longitude: 21.0 } }));
    expect(result.current.position).toEqual([52.2, 21.0]);
    expect(result.current.getTrack()).toHaveLength(1);
    act(() => {
      vi.advanceTimersByTime(50_000);
    });
    expect(result.current.getTrack()).toHaveLength(3);
  });

  it('stops watching and clears the timer when it unmounts', () => {
    const { unmount } = renderHook(() => useLocationTrack());
    unmount();
    expect(clearWatch).toHaveBeenCalledWith(7);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('explains the HTTPS requirement when the page is not secure', () => {
    expect(geoErrorText(true)).toContain('HTTPS');
    expect(geoErrorText(false)).not.toContain('HTTPS');
  });
});
