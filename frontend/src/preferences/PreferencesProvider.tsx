import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useHistory } from '../history/HistoryProvider';
import {
  applyHistory,
  DEFAULT_PREFERENCES,
  effectivePreferences,
  type AutoSpeeds,
  sanitizeStored,
  type Preferences,
  type StoredPreferences,
  type TimeRule,
} from './model';

interface PreferencesValue {
  /** Saved preferences, without time rules. */
  base: Preferences;
  rules: TimeRule[];
  /** Preferences valid right now (base + the active time rule + the average speeds from the history). */
  effective: Preferences;
  /** Speeds taken from the trip history instead of the configured ones. */
  autoUsed: AutoSpeeds;
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
  autoUsed: {},
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
  const { summary } = useHistory();

  // Time rules start and end on the clock: check every minute. The clock state changes only when the
  // active rule changes, so the rest of the app does not re-render every minute for nothing.
  const storedRef = useRef(stored);
  useEffect(() => {
    storedRef.current = stored;
  }, [stored]);
  useEffect(() => {
    const activeId = (at: Date) =>
      effectivePreferences(storedRef.current.base, storedRef.current.rules, at).activeRule?.id ?? null;
    const id = setInterval(() => {
      const next = new Date();
      setNow((prev) => (activeId(prev) === activeId(next) ? prev : next));
    }, 60_000);
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
    const { prefs: ruled, activeRule } = effectivePreferences(stored.base, stored.rules, now);
    const { prefs, used } = applyHistory(ruled, summary);
    return { base: stored.base, rules: stored.rules, effective: prefs, autoUsed: used, activeRule, setBase, setRules, reset };
  }, [stored, now, summary, setBase, setRules, reset]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export const usePreferences = () => useContext(PreferencesContext);
