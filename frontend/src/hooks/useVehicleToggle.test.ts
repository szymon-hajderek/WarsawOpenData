import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useVehicleDetection } from './useVehicleDetection';
import { BUS_POPUP_REQUEST_EVENT } from '../api/vehicle';

const input = { position: null, geoError: false, getTrack: () => [] };

describe('the bus button (toggle)', () => {
  it('first click asks for a detection and shows the window, the second hides it', () => {
    const asked = vi.fn();
    window.addEventListener(BUS_POPUP_REQUEST_EVENT, asked);
    const { result } = renderHook(() => useVehicleDetection(input));
    expect(result.current.open).toBe(false);

    act(() => result.current.toggle());
    expect(asked).toHaveBeenCalledTimes(1);
    expect(result.current.open).toBe(true);

    act(() => result.current.toggle());
    expect(result.current.open).toBe(false);
    expect(asked).toHaveBeenCalledTimes(1); // hiding does not detect again
    window.removeEventListener(BUS_POPUP_REQUEST_EVENT, asked);
  });

  it('hiding keeps the confirmed vehicle and showing it again does not detect again', () => {
    const asked = vi.fn();
    window.addEventListener(BUS_POPUP_REQUEST_EVENT, asked);
    const { result } = renderHook(() => useVehicleDetection(input));
    act(() => result.current.toggle()); // open (asked once)
    act(() => {
      result.current.selectManualLine('175'); // a hand-picked line ...
    });
    act(() => result.current.confirm()); // ... confirmed
    expect(result.current.confirmed?.line).toBe('175');

    act(() => result.current.toggle()); // hide
    expect(result.current.open).toBe(false);
    expect(result.current.confirmed?.line).toBe('175');

    act(() => result.current.toggle()); // show again
    expect(result.current.open).toBe(true);
    expect(asked).toHaveBeenCalledTimes(1);
    window.removeEventListener(BUS_POPUP_REQUEST_EVENT, asked);
  });

  it('hide() closes the window but keeps the confirmed vehicle (dismiss() forgets it)', () => {
    const { result } = renderHook(() => useVehicleDetection(input));
    act(() => result.current.toggle());
    act(() => {
      result.current.selectManualLine('175');
    });
    act(() => result.current.confirm());
    act(() => result.current.hide());
    expect(result.current.open).toBe(false);
    expect(result.current.confirmed?.line).toBe('175');

    act(() => result.current.toggle()); // back
    act(() => result.current.dismiss());
    expect(result.current.open).toBe(false);
    expect(result.current.confirmed).toBeNull();
  });
});
