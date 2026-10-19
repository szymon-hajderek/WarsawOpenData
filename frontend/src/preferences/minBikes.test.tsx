import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { DEFAULT_PREFERENCES, routeSearchBody, sanitizeStored } from './model';
import { CyclingSection } from '../components/preferences/PreferenceFields';

describe('bikes at the Veturilo dock', () => {
  it('asks for at least one bike by default and sends the choice', () => {
    expect(routeSearchBody(DEFAULT_PREFERENCES).minBikes).toBe(1);
    const prefs = { ...DEFAULT_PREFERENCES, cycling: { ...DEFAULT_PREFERENCES.cycling, minBikes: 3 } };
    expect(routeSearchBody(prefs).minBikes).toBe(3);
  });

  it('fills the default into older stored preferences', () => {
    const old = { base: { cycling: { enabled: true, level: 'sport', customKmh: null, autoSpeed: false } } };
    expect(sanitizeStored(old).base.cycling.minBikes).toBe(1);
  });

  it('is picked in the cycling section', () => {
    const onChange = vi.fn();
    render(<CyclingSection value={DEFAULT_PREFERENCES.cycling} onChange={onChange} />);
    expect(screen.getByRole('button', { name: '1+' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: '5+' }));
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_PREFERENCES.cycling, minBikes: 5 });
  });
});
