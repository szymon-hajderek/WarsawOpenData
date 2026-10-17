import { alpha, createTheme, type PaletteMode, type Theme } from '@mui/material';
import { LOOKS, type MapLook } from './map/looks';

/**
 * Material design theme. Colours come from the chosen look (`src/map/looks.ts`), so the accent
 * of the whole UI follows the map look; light / dark follows the colour mode.
 */
export function createAppTheme(mode: PaletteMode, look: MapLook): Theme {
  const { theme } = LOOKS[look][mode];
  return createTheme({
    palette: {
      mode,
      primary: theme.primary,
      secondary: theme.secondary,
      background: theme.background,
      divider: theme.divider,
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
      // Selected toggle buttons use the accent of the look instead of the default grey
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
