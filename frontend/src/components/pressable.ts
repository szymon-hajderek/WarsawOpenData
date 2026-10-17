import type { KeyboardEvent } from 'react';

/**
 * Props that make a card a keyboard-friendly toggle button (Enter and Space select it).
 * Space does not scroll the page, and keys pressed inside a child control are left alone.
 */
export function pressableProps(selected: boolean, onSelect: () => void) {
  return {
    role: 'button',
    tabIndex: 0,
    'aria-pressed': selected,
    onClick: onSelect,
    onKeyDown: (e: KeyboardEvent<HTMLElement>) => {
      if (e.target !== e.currentTarget) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onSelect();
      }
    },
  };
}
