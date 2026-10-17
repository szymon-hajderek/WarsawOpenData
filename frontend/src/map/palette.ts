/**
 * The colours of the app (Warsaw: red + yellow), light and dark. They set the map, its buttons and
 * markers AND the accent of the whole UI (see `src/theme.ts`). Every colour lives in this file.
 */
export type StyleMode = 'light' | 'dark';

/** Colours of the flat map style (see `src/map/mapStyle.ts`). */
export interface MapColors {
  background: string;
  water: string;
  park: string;
  wood: string;
  building: string;
  roadMinor: string;
  roadMinorCasing: string;
  roadMajor: string;
  roadMajorCasing: string;
  path: string;
  rail: string;
  label: string;
  labelSoft: string;
  labelHalo: string;
  waterLabel: string;
}

interface ThemeColors {
  primary: { main: string; contrastText: string };
  secondary: { main: string; contrastText: string };
  background: { default: string; paper: string };
  divider: string;
}

export interface Palette {
  map: MapColors;
  theme: ThemeColors;
  /** Colour of the map buttons' icons, the "me" and destination markers and walking legs. */
  accent: string;
  /** Soft background of round markers. */
  markerTint: string;
  /** Surface of floating map elements (buttons, marker rings, route casing). */
  surface: string;
  shadow: string;
  /** Start and destination colours of the line in the search card (start -> end). */
  routeStart: string;
  routeEnd: string;
}

export const PALETTE: Record<StyleMode, Palette> = {
  // Red is the main colour in light mode, yellow is an addition (and the main accent at night).
  light: {
    map: {
      background: '#FBF7EF',
      water: '#C9DDEE',
      park: '#CFE0B8',
      wood: '#DCE8C8',
      building: '#F6E3A8',
      roadMinor: '#FFFFFF',
      roadMinorCasing: '#EDE4D4',
      roadMajor: '#FFFFFF',
      roadMajorCasing: '#E6CFC4',
      path: '#EAE0D0',
      rail: '#D9A3A0',
      label: '#4A3B38',
      labelSoft: '#8A7670',
      labelHalo: '#FBF7EF',
      waterLabel: '#6D8FAE',
    },
    theme: {
      primary: { main: '#C8102E', contrastText: '#FFFFFF' },
      // dark gold: readable on white, still reads as "yellow"
      secondary: { main: '#A87400', contrastText: '#FFFFFF' },
      background: { default: '#FBF7EF', paper: '#FFFFFF' },
      divider: 'rgba(74,40,30,0.12)',
    },
    accent: '#C8102E',
    markerTint: '#FFF0C2',
    surface: '#FFFFFF',
    shadow: '0 6px 18px rgba(160, 20, 40, 0.25)',
    routeStart: '#E8A800',
    routeEnd: '#C8102E',
  },
  dark: {
    map: {
      background: '#1A1415',
      water: '#1D2C42',
      park: '#233A2D',
      wood: '#20332A',
      building: '#33291A',
      roadMinor: '#3B3032',
      roadMinorCasing: '#1A1415',
      roadMajor: '#54423F',
      roadMajorCasing: '#1A1415',
      path: '#2D2426',
      rail: '#7A4A4A',
      label: '#EFDFD6',
      labelSoft: '#A8928A',
      labelHalo: '#1A1415',
      waterLabel: '#7FA3CC',
    },
    theme: {
      primary: { main: '#FFC72C', contrastText: '#2A1B00' },
      secondary: { main: '#FF7A7A', contrastText: '#2A0000' },
      background: { default: '#140F10', paper: '#1F1819' },
      divider: 'rgba(255,255,255,0.10)',
    },
    accent: '#FFC72C',
    markerTint: '#3D3320',
    surface: '#2A2123',
    shadow: '0 6px 18px rgba(0, 0, 0, 0.5)',
    routeStart: '#FFC72C',
    routeEnd: '#FF7A7A',
  },
};

