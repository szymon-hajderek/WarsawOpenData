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
    background: '#FFE9CF',
    water: '#8ECBF8',
    park: '#DCEFA0',
    wood: '#CCE88C',
    building: 'rgba(255, 72, 96, 0.3)',
    buildingShadow: 'rgba(214, 0, 40, 0.3)',
    edge: '#FFFFFF',
    roadMinor: '#FFFFFF',
    roadMinorCasing: '#FFD27A',
    roadMajor: '#FFF3A6',
    roadMajorCasing: '#FFB000',
    roadGlow: 'rgba(255, 255, 255, 0.95)',
    roadMajorGlow: 'rgba(255, 120, 30, 0.5)',
    path: 'rgba(255, 255, 255, 0.9)',
    rail: '#FF3D5A',
    label: '#59102A',
    labelSoft: '#9A4B5E',
    labelHalo: 'rgba(255, 244, 226, 0.95)',
    waterLabel: '#2F78C4',
    sheenYellow: 'rgba(255, 205, 30, 0.38)',
    sheenRed: 'rgba(255, 40, 80, 0.26)',
    sheenBand: 'rgba(255, 255, 255, 0.55)',
    glassTop: 'rgba(255, 255, 255, 0.7)',
    glassBottom: 'rgba(255, 255, 255, 0.3)',
    glassBorder: 'rgba(255, 255, 255, 0.95)',
    glassHighlight: 'rgba(255, 255, 255, 1)',
  },
  dark: {
    background: '#1B1226',
    water: '#183A6E',
    park: '#203B3A',
    wood: '#1B3434',
    building: 'rgba(255, 176, 130, 0.16)',
    buildingShadow: 'rgba(8, 2, 14, 0.55)',
    edge: 'rgba(255, 232, 205, 0.55)',
    roadMinor: 'rgba(255, 226, 196, 0.34)',
    roadMinorCasing: '#2A1B33',
    roadMajor: '#F4BE55',
    roadMajorCasing: '#4A2F3A',
    roadGlow: 'rgba(255, 130, 120, 0.16)',
    roadMajorGlow: 'rgba(255, 190, 80, 0.38)',
    path: 'rgba(255, 226, 196, 0.2)',
    rail: '#C9788A',
    label: '#FFF0E2',
    labelSoft: '#C7A9B0',
    labelHalo: 'rgba(27, 18, 38, 0.92)',
    waterLabel: '#9DBFF2',
    sheenYellow: 'rgba(255, 190, 80, 0.16)',
    sheenRed: 'rgba(255, 90, 120, 0.2)',
    sheenBand: 'rgba(255, 240, 225, 0.16)',
    glassTop: 'rgba(255, 255, 255, 0.24)',
    glassBottom: 'rgba(255, 255, 255, 0.07)',
    glassBorder: 'rgba(255, 255, 255, 0.5)',
    glassHighlight: 'rgba(255, 255, 255, 0.65)',
  },
};
