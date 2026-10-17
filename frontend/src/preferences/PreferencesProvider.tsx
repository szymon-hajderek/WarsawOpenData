import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  DEFAULT_PREFERENCES,
  effectivePreferences,
  sanitizeStored,
  type Preferences,
  type StoredPreferences,
  type TimeRule,
} from './model';

interface PreferencesValue {
  /** Saved preferences, without time rules. */
  base: Preferences;
  rules: TimeRule[];
  /** Preferences valid right now (base + the active time rule). */
  effective: Preferences;
  activeRule: TimeRule | null;
  setBase: (next: Preferences) => void;
  setRules: (next: TimeRule[]) => void;
  reset: () => void;
}

const STORAGE_KEY = 'preferences';
const DEFAULT_STORED: StoredPreferences = { version: 1, base: DEFAULT_PREFERENCES, rules: [] };

const PreferencesContext = createContext<PreferencesValue>({
  base: DEFAULT_PREFERENCES,
  rules: [],
  effective: DEFAULT_PREFERENCES,
  activeRule: null,
  setBase: () => {},
  setRules: () => {},
  reset: () => {},
});

function load(): StoredPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? sanitizeStored(JSON.parse(raw)) : DEFAULT_STORED;
  } catch {
    return DEFAULT_STORED;
  }
}

/** Keeps the user's preferences and time rules in memory and in localStorage (no accounts yet). */
export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<StoredPreferences>(load);
  const [now, setNow] = useState(() => new Date());

  // Time rules start and end on the clock: re-evaluate every minute.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
    } catch {
      /* storage unavailable */
    }
  }, [stored]);

  const setBase = useCallback((base: Preferences) => setStored((s) => ({ ...s, base })), []);
  const setRules = useCallback((rules: TimeRule[]) => setStored((s) => ({ ...s, rules })), []);
  const reset = useCallback(() => setStored(DEFAULT_STORED), []);

  const value = useMemo<PreferencesValue>(() => {
    const { prefs, activeRule } = effectivePreferences(stored.base, stored.rules, now);
    return { base: stored.base, rules: stored.rules, effective: prefs, activeRule, setBase, setRules, reset };
  }, [stored, now, setBase, setRules, reset]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export const usePreferences = () => useContext(PreferencesContext);
