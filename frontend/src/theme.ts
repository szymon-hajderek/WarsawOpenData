import { createTheme, type PaletteMode, type Theme } from '@mui/material';

/**
 * Material design theme. Every colour lives here, so adding/changing a colour
 * scheme means touching this file only (the app switches between light and dark).
 */
export function createAppTheme(mode: PaletteMode): Theme {
  const dark = mode === 'dark';
  return createTheme({
    palette: {
      mode,
      primary: {
        main: dark ? '#B6BEFF' : '#4355C7',
        contrastText: dark ? '#0E1226' : '#FFFFFF',
      },
      secondary: {
        main: dark ? '#4DD6C0' : '#00897B',
        contrastText: dark ? '#00201B' : '#FFFFFF',
      },
      background: {
        default: dark ? '#0E1116' : '#F4F6FB',
        paper: dark ? '#171B22' : '#FFFFFF',
      },
      divider: dark ? 'rgba(255,255,255,0.10)' : 'rgba(20,28,60,0.10)',
    },
    shape: { borderRadius: 16 },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      button: { textTransform: 'none', fontWeight: 600, letterSpacing: 0.1 },
    },
    components: {
      MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiButton: {
        styleOverrides: { root: { borderRadius: 999, paddingBlock: 12 } },
      },
      MuiChip: { styleOverrides: { root: { fontWeight: 500 } } },
    },
  });
}
