import { afterEach, describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { setMapLook, useMapLook } from './mapLook';

describe('map look', () => {
  afterEach(() => {
    act(() => setMapLook('flat'));
    localStorage.clear();
  });

  it('starts flat and is remembered on the device', () => {
    const { result } = renderHook(() => useMapLook());
    expect(result.current[0]).toBe('flat');
    act(() => setMapLook('glass'));
    expect(result.current[0]).toBe('glass');
    expect(localStorage.getItem('map-look')).toBe('glass');
  });

  it('every map follows a change made elsewhere (Preferences)', () => {
    const a = renderHook(() => useMapLook());
    const b = renderHook(() => useMapLook());
    act(() => setMapLook('glass'));
    expect(a.result.current[0]).toBe('glass');
    expect(b.result.current[0]).toBe('glass');
  });

  it('the toggle switches between the two looks', () => {
    const { result } = renderHook(() => useMapLook());
    act(() => result.current[1]());
    expect(result.current[0]).toBe('glass');
    act(() => result.current[1]());
    expect(result.current[0]).toBe('flat');
  });
});
