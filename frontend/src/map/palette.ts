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


/** Colours of the "liquid glass" map look (second version of the map; same red + yellow). */
export interface GlassColors extends MapColors {
  /** Soft shadow of the glass building tiles, offset to the south-east. */
  buildingShadow: string;
  /** Bright edge of glass (building tiles, shore). */
  edge: string;
  /** Wide blurred glow under the roads. */
  roadGlow: string;
  roadMajorGlow: string;
  /** Moving light over the map. */
  sheenYellow: string;
  sheenRed: string;
  sheenBand: string;
  /** Glass of the round buttons and markers. */
  glassTop: string;
  glassBottom: string;
  glassBorder: string;
  glassHighlight: string;
}

export const GLASS: Record<StyleMode, GlassColors> = {
  light: {
    background: '#FFF4E6',
    water: '#C4DCF2',
    park: '#E6EEC3',
    wood: '#DDE9BC',
    building: 'rgba(255, 228, 165, 0.45)',
    buildingShadow: 'rgba(200, 16, 46, 0.13)',
    edge: 'rgba(255, 255, 255, 0.95)',
    roadMinor: '#FFFFFF',
    roadMinorCasing: '#FFE3C2',
    roadMajor: '#FFF3CF',
    roadMajorCasing: '#FFC66B',
    roadGlow: 'rgba(255, 255, 255, 0.85)',
    roadMajorGlow: 'rgba(255, 150, 60, 0.4)',
    path: 'rgba(255, 255, 255, 0.8)',
    rail: '#E88C94',
    label: '#4A2630',
    labelSoft: '#8C6670',
    labelHalo: 'rgba(255, 246, 232, 0.95)',
    waterLabel: '#5F86B0',
    sheenYellow: 'rgba(255, 199, 44, 0.22)',
    sheenRed: 'rgba(200, 16, 46, 0.12)',
    sheenBand: 'rgba(255, 255, 255, 0.3)',
    glassTop: 'rgba(255, 255, 255, 0.72)',
    glassBottom: 'rgba(255, 255, 255, 0.34)',
    glassBorder: 'rgba(255, 255, 255, 0.85)',
    glassHighlight: 'rgba(255, 255, 255, 0.95)',
  },
  dark: {
    background: '#1C1113',
    water: '#1B2A47',
    park: '#26362C',
    wood: '#22322A',
    building: 'rgba(255, 199, 44, 0.16)',
    buildingShadow: 'rgba(0, 0, 0, 0.55)',
    edge: 'rgba(255, 214, 120, 0.6)',
    roadMinor: '#54393C',
    roadMinorCasing: '#2A1B1E',
    roadMajor: '#9A7428',
    roadMajorCasing: '#4E3716',
    roadGlow: 'rgba(255, 122, 122, 0.22)',
    roadMajorGlow: 'rgba(255, 199, 44, 0.22)',
    path: 'rgba(255, 255, 255, 0.18)',
    rail: '#B0636B',
    label: '#FBE9DC',
    labelSoft: '#B89A92',
    labelHalo: 'rgba(28, 17, 19, 0.92)',
    waterLabel: '#86A9D6',
    sheenYellow: 'rgba(255, 199, 44, 0.16)',
    sheenRed: 'rgba(255, 90, 100, 0.14)',
    sheenBand: 'rgba(255, 255, 255, 0.12)',
    glassTop: 'rgba(255, 255, 255, 0.2)',
    glassBottom: 'rgba(255, 255, 255, 0.06)',
    glassBorder: 'rgba(255, 255, 255, 0.28)',
    glassHighlight: 'rgba(255, 255, 255, 0.45)',
  },
};
