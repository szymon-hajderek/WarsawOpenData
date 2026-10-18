import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import PlaceField from './PlaceField';
import { FrequentPlacesProvider } from '../places/FrequentPlacesProvider';
import { STORAGE_KEY, type FrequentPlace } from '../places/frequentPlaces';

describe('PlaceField frequent places', () => {
  it('suggests a frequent place in an empty field', () => {
    const saved: FrequentPlace[] = [
      { id: 'stop-1', label: 'Politechnika', sublabel: 'Przystanek', position: [52.22, 21.01], score: 3, lastAt: Date.now() },
    ];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    render(
      <FrequentPlacesProvider>
        <PlaceField value={null} onChange={() => {}} placeholder="Dokąd jedziesz?" currentLocation={null} />
      </FrequentPlacesProvider>,
    );
    fireEvent.mouseDown(screen.getByLabelText('Dokąd jedziesz?'));
    expect(screen.getByText('Politechnika')).toBeTruthy();
    expect(screen.getByText('Często wybierane · Przystanek')).toBeTruthy();
    localStorage.removeItem(STORAGE_KEY);
  });
});
