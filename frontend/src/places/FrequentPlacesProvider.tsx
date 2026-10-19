import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { Place } from '../types';
import { loadFrequent, recordPlaces, saveFrequent, type FrequentPlace } from './frequentPlaces';

interface FrequentValue {
  places: FrequentPlace[];
  /** Counts the places of one route search. */
  record: (places: Place[]) => void;
  clear: () => void;
}

const FrequentContext = createContext<FrequentValue>({ places: [], record: () => {}, clear: () => {} });

/** Keeps the user's frequent places on this device (see `frequentPlaces.ts`). */
export function FrequentPlacesProvider({ children }: { children: ReactNode }) {
  const [places, setPlaces] = useState<FrequentPlace[]>(loadFrequent);

  const record = useCallback((found: Place[]) => {
    setPlaces((old) => {
      const next = recordPlaces(old, found, Date.now());
      saveFrequent(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    saveFrequent([]);
    setPlaces([]);
  }, []);

  const value = useMemo(() => ({ places, record, clear }), [places, record, clear]);
  return <FrequentContext.Provider value={value}>{children}</FrequentContext.Provider>;
}

export const useFrequentPlaces = () => useContext(FrequentContext);
