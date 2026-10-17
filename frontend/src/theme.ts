import { alpha, createTheme, type PaletteMode, type Theme } from '@mui/material';
import { PALETTE } from './map/palette';
import { RADIUS } from './layout';

/**
 * Material design theme. Colours come from `src/map/palette.ts`; light / dark follows the colour mode.
 */
export function createAppTheme(mode: PaletteMode): Theme {
  const { theme } = PALETTE[mode];
  return createTheme({
    palette: {
      mode,
      primary: theme.primary,
      secondary: theme.secondary,
      background: theme.background,
      divider: theme.divider,
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
      button: { textTransform: 'none', fontWeight: 600, letterSpacing: 0.1 },
    },
    components: {
      MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiButton: {
        styleOverrides: { root: { borderRadius: RADIUS.pill, paddingBlock: 12 } },
      },
      MuiChip: { styleOverrides: { root: { fontWeight: 500 } } },
      MuiDialog: { styleOverrides: { paper: { borderRadius: RADIUS.sheet } } },
      // Selected toggle buttons use the accent colour instead of the default grey
      MuiToggleButton: {
        styleOverrides: {
          root: ({ theme: t }) => ({
            '&.Mui-selected': {
              backgroundColor: alpha(t.palette.primary.main, 0.18),
              color: t.palette.primary.main,
              '&:hover': { backgroundColor: alpha(t.palette.primary.main, 0.26) },
            },
          }),
        },
      },
    },
  });
}
