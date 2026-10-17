import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { CssBaseline, ThemeProvider, type PaletteMode } from '@mui/material';
import { createAppTheme } from './theme';
import { useMapLook } from './mapLook';

interface ColorModeValue {
  mode: PaletteMode;
  toggle: () => void;
}

const ColorModeContext = createContext<ColorModeValue>({ mode: 'light', toggle: () => {} });
const STORAGE_KEY = 'color-mode';

function initialMode(): PaletteMode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
  } catch {
    /* storage unavailable */
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<PaletteMode>(initialMode);
  const { look } = useMapLook();

  const toggle = useCallback(() => {
    setMode((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }, []);

  const theme = useMemo(() => createAppTheme(mode, look), [mode, look]);
  const value = useMemo(() => ({ mode, toggle }), [mode, toggle]);

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export const useColorMode = () => useContext(ColorModeContext);
