import { useState, type ReactNode } from 'react';
import { Box, Checkbox, FormControlLabel, IconButton, Popover, Typography, type PaletteMode } from '@mui/material';
import MyLocation from '@mui/icons-material/MyLocation';
import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import DirectionsBus from '@mui/icons-material/DirectionsBus';
import Signpost from '@mui/icons-material/Signpost';
import ThreeDRotation from '@mui/icons-material/ThreeDRotation';
import ThreeSixty from '@mui/icons-material/ThreeSixty';
import { PALETTE } from '../map/palette';
import { OVERLAYS, type OverlayId } from '../map/overlays';
import { glassStyle } from '../map/glass';
import { useMapLook } from '../map/mapLook';
import '../map/glass.css';

interface Props {
  paletteMode: PaletteMode;
  onToggleMode: () => void;
  /** The map being shown: the button switches to the other one. */
  view3d: boolean;
  onSwitchView: () => void;
  overlayIds: OverlayId[];
  onToggleOverlay: (id: OverlayId) => void;
  /** A switched-on stop layer is hidden because the map is zoomed out too far. */
  overlayZoomedOut: boolean;
  onLocate: () => void;
  /** Shows a button that detects the vehicle the user is in (and reopens the vehicle window). */
  onDetectVehicle?: () => void;
  /** The 3D map only: the rotate mode (one finger turns and tilts the map instead of moving it). */
  rotate?: { on: boolean; onToggle: () => void };
  /** Extra top offset (px) on phones, when the search card grows. */
  controlsOffset?: number;
}

/**
 * The round buttons on the right of both maps (2D and 3D): the same buttons in the same order, so nothing moves when the
 * map is switched. 2D / 3D switch, theme, stop layers, vehicle detection, my location.
 * The look of the map (flat / glass) is a setting in Preferences ("Widok"), not a button here.
 */
export default function MapControls({
  paletteMode,
  onToggleMode,
  view3d,
  onSwitchView,
  overlayIds,
  onToggleOverlay,
  overlayZoomedOut,
  onLocate,
  onDetectVehicle,
  rotate,
  controlsOffset = 0,
}: Props) {
  const colors = PALETTE[paletteMode];
  const [look] = useMapLook();
  const glass = look === 'glass';
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  const fab = (child: ReactNode) => (
    <Box
      className={glass ? 'glass-rim' : undefined}
      sx={{
        borderRadius: '50%',
        ...(glass ? glassStyle(paletteMode) : { bgcolor: colors.surface, boxShadow: colors.shadow }),
        '& .MuiIconButton-root': { width: 46, height: 46, color: colors.accent, fontWeight: 800, fontSize: 15 },
      }}
    >
      {child}
    </Box>
  );

  return (
    <Box
      sx={{
        position: 'absolute',
        zIndex: 900,
        right: { xs: 12, sm: 16 },
        top: { xs: `calc(env(safe-area-inset-top) + ${156 + controlsOffset}px)`, sm: 'calc(env(safe-area-inset-top) + 16px)' },
        display: 'flex',
        flexDirection: 'column',
        gap: 1.25,
      }}
    >
      {fab(
        <IconButton aria-label={view3d ? 'Wróć do mapy 2D' : 'Włącz mapę 3D (prototyp)'} onClick={onSwitchView}>
          {view3d ? '2D' : <ThreeDRotation />}
        </IconButton>,
      )}
      {fab(
        <IconButton aria-label={paletteMode === 'dark' ? 'Włącz jasny motyw' : 'Włącz ciemny motyw'} onClick={onToggleMode}>
          {paletteMode === 'dark' ? <LightMode /> : <DarkMode />}
        </IconButton>,
      )}
      {fab(
        <IconButton
          aria-label="Warstwy przystanków"
          aria-haspopup="dialog"
          aria-pressed={overlayIds.length > 0}
          onClick={(e) => setAnchor(e.currentTarget)}
        >
          <Signpost />
        </IconButton>,
      )}
      <Popover
        open={anchor !== null}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { borderRadius: '16px', mr: 1 } } }}
      >
        <Box role="dialog" aria-label="Warstwy przystanków" sx={{ px: 2, py: 1.5, display: 'flex', flexDirection: 'column' }}>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Pokaż na mapie
          </Typography>
          {OVERLAYS.map((o) => (
            <FormControlLabel
              key={o.id}
              control={<Checkbox size="small" checked={overlayIds.includes(o.id)} onChange={() => onToggleOverlay(o.id)} />}
              label={o.label}
            />
          ))}
          {overlayZoomedOut && (
            <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 200 }}>
              Przybliż mapę, aby zobaczyć przystanki.
            </Typography>
          )}
        </Box>
      </Popover>
      {onDetectVehicle &&
        fab(
          <IconButton aria-label="Wykryj pojazd, w którym jesteś" onClick={onDetectVehicle}>
            <DirectionsBus />
          </IconButton>,
        )}
      {fab(
        <IconButton aria-label="Moja lokalizacja" onClick={onLocate}>
          <MyLocation />
        </IconButton>,
      )}
      {rotate &&
        fab(
          <IconButton aria-label="Obracanie mapy palcem" aria-pressed={rotate.on} onClick={rotate.onToggle} sx={rotate.on ? { bgcolor: 'action.selected' } : undefined}>
            <ThreeSixty />
          </IconButton>,
        )}
    </Box>
  );
}
