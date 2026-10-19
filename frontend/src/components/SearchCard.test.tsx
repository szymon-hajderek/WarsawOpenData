import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import SearchCard from './SearchCard';

const base = {
  origin: { id: 'o', label: 'Politechnika', position: [52.22, 21.01] as [number, number] },
  destination: null,
  stops: [],
  order: 'given' as const,
  currentLocation: null,
  onOriginChange: vi.fn(),
  onDestinationChange: vi.fn(),
  onStopsChange: vi.fn(),
  onOrderChange: vi.fn(),
  onSwap: vi.fn(),
  onLocate: vi.fn(),
};

describe('SearchCard collapsing', () => {
  it('collapsed: only "Dokąd jedziesz?" and the chevron, no start field', () => {
    render(<SearchCard {...base} collapsed onToggleCollapsed={vi.fn()} />);
    expect(screen.getByPlaceholderText('Dokąd jedziesz?')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Skąd jedziesz?')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Rozwiń wyszukiwanie/)).toBeInTheDocument();
  });

  it('the chevron asks to open the card', () => {
    const toggle = vi.fn();
    render(<SearchCard {...base} collapsed onToggleCollapsed={toggle} />);
    fireEvent.click(screen.getByLabelText(/Rozwiń wyszukiwanie/));
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it('open: both fields, and a chevron that folds it', () => {
    const toggle = vi.fn();
    render(<SearchCard {...base} collapsed={false} onToggleCollapsed={toggle} />);
    expect(screen.getByPlaceholderText('Skąd jedziesz?')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Dokąd jedziesz?')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Zwiń wyszukiwanie'));
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it('collapsed with a destination but no start offers "Ustaw start"', () => {
    const toggle = vi.fn();
    render(
      <SearchCard
        {...base}
        origin={null}
        destination={{ id: 'd', label: 'Centrum', position: [52.23, 21.0] }}
        collapsed
        onToggleCollapsed={toggle}
      />,
    );
    fireEvent.click(screen.getByText('Ustaw start'));
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it('without the toggle (the ride demo) it is always open', () => {
    render(<SearchCard {...base} collapsed />);
    expect(screen.getByPlaceholderText('Skąd jedziesz?')).toBeInTheDocument();
  });

  it('a new search during a trip is never collapsed (it holds "Wróć do przejazdu")', () => {
    render(<SearchCard {...base} collapsed onToggleCollapsed={vi.fn()} onBackToTrip={vi.fn()} />);
    expect(screen.getByText(/Wróć do przejazdu/)).toBeInTheDocument();
  });
});
