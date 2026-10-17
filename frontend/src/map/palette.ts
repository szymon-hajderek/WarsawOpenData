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
    water: '#86C8FF',
    park: '#D9F28E',
    wood: '#C8EA78',
    building: 'rgba(255, 64, 88, 0.36)',
    buildingShadow: 'rgba(214, 0, 40, 0.3)',
    edge: '#FFFFFF',
    roadMinor: '#FFFFFF',
    roadMinorCasing: '#FFD27A',
    roadMajor: '#FFF3A6',
    roadMajorCasing: '#FFB000',
    roadGlow: 'rgba(255, 255, 255, 0.95)',
    roadMajorGlow: 'rgba(255, 110, 20, 0.65)',
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
    background: '#150710',
    water: '#0C2C78',
    park: '#12402C',
    wood: '#0F3825',
    building: 'rgba(255, 40, 80, 0.3)',
    buildingShadow: 'rgba(0, 0, 0, 0.6)',
    edge: 'rgba(255, 224, 130, 0.95)',
    roadMinor: '#FF5C74',
    roadMinorCasing: '#5A1028',
    roadMajor: '#FFD60A',
    roadMajorCasing: '#B36B00',
    roadGlow: 'rgba(255, 50, 90, 0.6)',
    roadMajorGlow: 'rgba(255, 214, 10, 0.7)',
    path: 'rgba(255, 190, 200, 0.4)',
    rail: '#FF8A9A',
    label: '#FFF1E6',
    labelSoft: '#D9A8A0',
    labelHalo: 'rgba(21, 7, 16, 0.95)',
    waterLabel: '#8FB4FF',
    sheenYellow: 'rgba(255, 214, 10, 0.3)',
    sheenRed: 'rgba(255, 40, 90, 0.34)',
    sheenBand: 'rgba(255, 255, 255, 0.3)',
    glassTop: 'rgba(255, 255, 255, 0.24)',
    glassBottom: 'rgba(255, 255, 255, 0.07)',
    glassBorder: 'rgba(255, 255, 255, 0.5)',
    glassHighlight: 'rgba(255, 255, 255, 0.65)',
  },
};
