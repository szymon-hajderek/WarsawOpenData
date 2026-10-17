import type { ElementType } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { PaletteMode } from '@mui/material';
import DirectionsWalk from '@mui/icons-material/DirectionsWalk';
import DirectionsBike from '@mui/icons-material/DirectionsBike';
import DirectionsBus from '@mui/icons-material/DirectionsBus';
import Tram from '@mui/icons-material/Tram';
import Subway from '@mui/icons-material/Subway';
import Train from '@mui/icons-material/Train';
import type { TransportMode } from './types';

interface ModeMeta {
  label: string;
  icon: ElementType;
  light: string;
  dark: string;
}

export const MODE_META: Record<TransportMode, ModeMeta> = {
  walk: { label: 'Pieszo', icon: DirectionsWalk, light: '#607D8B', dark: '#90A4AE' },
  bike: { label: 'Veturilo', icon: DirectionsBike, light: '#00897B', dark: '#2EE0C4' },
  bus: { label: 'Autobus', icon: DirectionsBus, light: '#D84315', dark: '#FF8A65' },
  tram: { label: 'Tramwaj', icon: Tram, light: '#F59E0B', dark: '#FBBF24' },
  metro: { label: 'Metro', icon: Subway, light: '#7B1FA2', dark: '#CE93D8' },
  rail: { label: 'Kolej', icon: Train, light: '#0288D1', dark: '#4FC3F7' },
};

export const modeColor = (mode: TransportMode, palette: PaletteMode): string =>
  MODE_META[mode][palette];

/** Material icon as an HTML string, for Leaflet divIcons. */
export function iconHtml(Icon: ElementType, size: number, color: string): string {
  return renderToStaticMarkup(
    <Icon style={{ width: size, height: size, fill: color, display: 'block' }} />,
  );
}
