import { fireEvent, screen, waitFor } from '@testing-library/react';

/**
 * On a phone the search card starts folded to "Dokąd jedziesz?"; tests that use the start field open it first.
 * On a wide screen (the side panel) the card is always open and nothing is clicked.
 */
export async function openSearchCard(): Promise<void> {
  await waitFor(() => {
    if (!screen.queryByPlaceholderText('Skąd jedziesz?') && !screen.queryByLabelText(/Rozwiń wyszukiwanie/)) throw new Error('no search card yet');
  });
  const open = screen.queryByLabelText(/Rozwiń wyszukiwanie/);
  if (open) fireEvent.click(open);
  await screen.findByPlaceholderText('Skąd jedziesz?');
}
