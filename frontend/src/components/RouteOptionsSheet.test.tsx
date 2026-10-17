import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import RouteOptionsSheet from './RouteOptionsSheet';
import type { RouteOption } from '../types';

const route = (id: string, title: string): RouteOption => ({
  id,
  title,
  legs: [{ mode: 'walk', from: 'A', to: 'B', durationMin: 5, distanceM: 300, path: [[52.2, 21.0], [52.21, 21.01]] }],
  departure: '10:00',
  arrival: '10:05',
  durationMin: 5,
  distanceM: 300,
  calories: 10,
  transfers: 0,
  costPln: 0,
  tags: [],
});

const props = {
  options: [route('a', 'Pieszo'), route('b', 'Tramwaj')],
  foundCount: 2,
  loading: false,
  error: false,
  mock: false,
  selectedId: 'a',
  summary: [],
  activeRule: null,
  chips: [],
  snap: 'middle' as const,
  onSnapChange: vi.fn(),
  onSelect: vi.fn(),
  onOpenFilters: vi.fn(),
  onClearChip: vi.fn(),
  onClearAll: vi.fn(),
  onConfirm: vi.fn(),
};

describe('RouteOptionsSheet', () => {
  it('selects a route with Enter and Space, and keeps Space from scrolling the page', () => {
    render(<RouteOptionsSheet {...props} />);
    const card = screen.getByText('Tramwaj').closest('[role="button"]') as HTMLElement;
    fireEvent.keyDown(card, { key: 'Enter' });
    expect(props.onSelect).toHaveBeenCalledWith('b');
    const notPrevented = fireEvent.keyDown(card, { key: ' ' });
    expect(notPrevented).toBe(false);
  });

  it('marks example data with a chip', () => {
    render(<RouteOptionsSheet {...props} mock />);
    expect(screen.getByText('Dane przykładowe')).toBeInTheDocument();
  });

  it('says so when the search failed', () => {
    render(<RouteOptionsSheet {...props} options={[]} foundCount={0} error />);
    expect(screen.getByText(/Nie udało się pobrać tras/)).toBeInTheDocument();
  });
});
