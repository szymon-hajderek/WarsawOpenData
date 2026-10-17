import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react';
import {
  alpha,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  TextField,
  Typography,
  useTheme,
  type Theme,
} from '@mui/material';
import Close from '@mui/icons-material/Close';
import Refresh from '@mui/icons-material/Refresh';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import { MODE_META, modeColor } from '../modes';
import type { VehicleCandidate } from '../types';
import { PANEL_BOTTOM, RADIUS } from '../layout';
import { formatDistance } from '../utils/format';
import { pressableProps } from './pressable';

const vehicleName = (v: VehicleCandidate) => `${MODE_META[v.mode].label} ${v.line}`;
/** "kier. X", or nothing when the direction is unknown (live buses have none yet). */
const directionText = (v: VehicleCandidate) => (v.direction ? `kier. ${v.direction}` : '');
/** Distance of the vehicle from the user, when the backend sent it. */
const distanceText = (v: VehicleCandidate) =>
  v.distanceM !== undefined ? `ok. ${formatDistance(v.distanceM)} od Ciebie` : '';

/** Heights the popup settles on: a bar, the middle (suggested vehicle + confirm) and the full popup. */
export type VehicleSnap = 'bar' | 'middle' | 'full';
const SNAPS: VehicleSnap[] = ['bar', 'middle', 'full'];
const BAR_H = 76;

function useViewport() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const onResize = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return size;
}

function snapHeights(vh: number, wide: boolean): Record<VehicleSnap, number> {
  const middle = Math.min(258, Math.round(vh * 0.5));
  const full = Math.max(middle + 90, wide ? vh - 200 : Math.round(vh * 0.62));
  return { bar: BAR_H, middle, full };
}

interface DragState {
  startY: number;
  startH: number;
  lastY: number;
  lastT: number;
  /** Speed of the finger, px per ms, positive = up. */
  v: number;
  moved: boolean;
}

/**
 * The sheet follows the finger and settles on the nearest snap height; a quick flick carries it
 * further (to the next snap). A tap steps up (bar -> middle -> full); on the full popup it steps back to the middle.
 */
function useSnapDrag(
  snap: VehicleSnap,
  heights: Record<VehicleSnap, number>,
  onSnap: (s: VehicleSnap) => void,
) {
  const drag = useRef<DragState | null>(null);
  const [liveH, setLiveH] = useState<number | null>(null);
  const height = liveH ?? heights[snap];
  const clamp = (h: number) => Math.min(heights.full, Math.max(heights.bar, h));

  const tap = () => onSnap(snap === 'bar' ? 'middle' : snap === 'middle' ? 'full' : 'middle');

  const handlers = {
    onPointerDown: (e: ReactPointerEvent<HTMLElement>) => {
      drag.current = { startY: e.clientY, startH: height, lastY: e.clientY, lastT: performance.now(), v: 0, moved: false };
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        /* pointer is not active (e.g. a synthetic event): dragging still works */
      }
    },
    onPointerMove: (e: ReactPointerEvent<HTMLElement>) => {
      const d = drag.current;
      if (!d) return;
      const dy = d.startY - e.clientY;
      if (Math.abs(dy) > 6) d.moved = true;
      if (!d.moved) return;
      const now = performance.now();
      const dt = Math.max(1, now - d.lastT);
      d.v = 0.7 * d.v + 0.3 * ((d.lastY - e.clientY) / dt);
      d.lastY = e.clientY;
      d.lastT = now;
      setLiveH(clamp(d.startH + dy));
    },
    onPointerUp: () => {
      const d = drag.current;
      drag.current = null;
      if (!d) return;
      if (!d.moved) {
        setLiveH(null);
        tap();
        return;
      }
      const projected = clamp((liveH ?? d.startH) + d.v * 180);
      const target = SNAPS.reduce((best, s) =>
        Math.abs(heights[s] - projected) < Math.abs(heights[best] - projected) ? s : best,
      );
      setLiveH(null);
      onSnap(target);
    },
    onPointerCancel: () => {
      drag.current = null;
      setLiveH(null);
    },
    onKeyDown: (e: ReactKeyboardEvent<HTMLElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        tap();
      } else if (e.key === 'ArrowUp') onSnap(SNAPS[Math.min(2, SNAPS.indexOf(snap) + 1)]);
      else if (e.key === 'ArrowDown') onSnap(SNAPS[Math.max(0, SNAPS.indexOf(snap) - 1)]);
    },
  };

  return { handlers, height, dragging: liveH !== null };
}

function ModeBadge({ vehicle, size = 44 }: { vehicle: VehicleCandidate; size?: number }) {
  const palette = useTheme().palette.mode;
  const color = modeColor(vehicle.mode, palette);
  const Icon = MODE_META[vehicle.mode].icon;
  return (
    <Box
      sx={{
        width: size,
        height: size,
        flexShrink: 0,
        borderRadius: '50%',
        display: 'grid',
        placeItems: 'center',
        bgcolor: alpha(color, 0.2),
        color,
      }}
    >
      <Icon sx={{ fontSize: size * 0.55 }} />
    </Box>
  );
}

interface Props {
  /** The most likely vehicle first, then up to 3 other possible ones. */
  candidates: VehicleCandidate[];
  /** All lines the user can pick by hand. */
  lines: string[];
  /** The line picked by hand, if any. */
  manual: VehicleCandidate | null;
  loading: boolean;
  /** The candidates are made-up example data. */
  mock: boolean;
  snap: VehicleSnap;
  selectedId: string | null;
  /** The vehicle the user confirmed (shown in the hidden bar). */
  confirmed: VehicleCandidate | null;
  onSnapChange: (snap: VehicleSnap) => void;
  onSelect: (id: string) => void;
  onManualLine: (line: string) => void;
  onClearManual: () => void;
  /** Detect the vehicle again. */
  onRedetect: () => void;
  onConfirm: () => void;
  /** "I am not in a vehicle". */
  onDismiss: () => void;
}

/**
 * "Which vehicle am I in?" window. It follows the finger and settles on three heights (bar, middle, full),
 * so it never has to take over the screen. Starts in the middle. Coloured by the theme.
 */
export default function VehicleSheet({
  candidates,
  lines,
  manual,
  loading,
  mock,
  snap,
  selectedId,
  confirmed,
  onSnapChange,
  onSelect,
  onManualLine,
  onClearManual,
  onRedetect,
  onConfirm,
  onDismiss,
}: Props) {
  const { w, h: vh } = useViewport();
  const heights = snapHeights(vh, w >= 600);
  const { handlers, height, dragging } = useSnapDrag(snap, heights, onSnapChange);
  // Content follows the live height while dragging: the bar summary below the middle point
  const barLike = height < (heights.bar + heights.middle) / 2;
  const full = height >= heights.full - 4;

  const suggested = candidates[0];
  const others = candidates.slice(1, 4);
  const selected = [...candidates, ...(manual ? [manual] : [])].find((c) => c.id === selectedId) ?? null;
  const shown = confirmed ?? suggested;

  const cardSx = (isSelected: boolean) => (t: Theme) => ({
    cursor: 'pointer',
    border: 2,
    borderColor: isSelected ? 'primary.main' : 'transparent',
    bgcolor: isSelected ? alpha(t.palette.primary.main, 0.1) : alpha(t.palette.primary.main, 0.05),
    transition: 'background-color .15s, border-color .15s',
    '&:hover': { bgcolor: alpha(t.palette.primary.main, isSelected ? 0.12 : 0.09) },
    '&:focus-visible': { outline: `2px solid ${t.palette.primary.main}`, outlineOffset: 2 },
  });
  const pressable = (c: VehicleCandidate) => pressableProps(c.id === selectedId, () => onSelect(c.id));

  return (
    <Paper
      elevation={8}
      sx={{
        position: 'absolute',
        zIndex: 1000,
        bottom: PANEL_BOTTOM,
        left: { xs: 8, sm: 16 },
        right: { xs: 8, sm: 'auto' },
        width: { sm: 440 },
        height,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: RADIUS.sheet,
        overflow: 'hidden',
        // follows the finger without delay, settles smoothly after the release
        transition: dragging ? 'none' : 'height 0.32s cubic-bezier(0.2, 0.8, 0.2, 1)',
      }}
    >
      {/* drag zone: handle + header. Drag to resize, tap or Enter to step */}
      <Box
        {...handlers}
        role="button"
        tabIndex={0}
        aria-label="W jakim pojeździe jesteś? Przeciągnij lub naciśnij Enter, aby zmienić wysokość okienka"
        aria-expanded={snap !== 'bar'}
        sx={{
          flexShrink: 0,
          touchAction: 'none',
          cursor: dragging ? 'grabbing' : 'grab',
          userSelect: 'none',
          px: 2.5,
          pb: barLike ? 1.5 : 1,
          '&:focus-visible': { outline: (t) => `2px solid ${t.palette.primary.main}`, outlineOffset: -2 },
        }}
      >
        <Box sx={{ display: 'grid', placeItems: 'center', py: 1.25 }}>
          <Box sx={{ width: 36, height: 4, borderRadius: RADIUS.pill, bgcolor: 'text.disabled', opacity: 0.5 }} />
        </Box>

        {!barLike ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.25 }}>
                W jakim pojeździe jesteś?
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                Sugerujemy na podstawie lokalizacji.
              </Typography>
            </Box>
            {full ? <ExpandMore color="action" /> : <ExpandLess color="action" />}
          </Box>
        ) : (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            {loading && !shown ? (
              <>
                <CircularProgress size={22} />
                <Typography sx={{ flex: 1 }}>Szukam pojazdu…</Typography>
              </>
            ) : shown ? (
              <>
                <ModeBadge vehicle={shown} size={40} />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography noWrap sx={{ fontWeight: 700 }}>
                    {confirmed ? `Jedziesz: ${vehicleName(shown)}` : vehicleName(shown)}
                  </Typography>
                  {directionText(shown) && (
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {directionText(shown)}
                    </Typography>
                  )}
                </Box>
                <Typography variant="body2" color="primary" sx={{ fontWeight: 700 }}>
                  {confirmed ? 'Zmień' : 'Pokaż'}
                </Typography>
                <ExpandLess color="primary" />
              </>
            ) : (
              <>
                <Typography sx={{ flex: 1 }}>Nie wykryto pojazdu</Typography>
                <ExpandLess color="action" />
              </>
            )}
          </Box>
        )}
      </Box>

      {!barLike && (
        <Box sx={{ flex: 1, minHeight: 0, overflowY: full && !dragging ? 'auto' : 'hidden', px: 2, pb: 2 }}>
          {/* primary block: visible in the middle height */}
          {loading && candidates.length === 0 && (
            <Box sx={{ display: 'grid', placeItems: 'center', py: 3 }}>
              <CircularProgress size={32} />
            </Box>
          )}

          {suggested && (
            <Box
              {...pressable(suggested)}
              sx={[{ display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, borderRadius: RADIUS.tile }, cardSx(suggested.id === selectedId)]}
            >
              <ModeBadge vehicle={suggested} size={52} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                    {vehicleName(suggested)}
                  </Typography>
                  <Chip label="Sugerowana" size="small" color="secondary" variant="outlined" />
                  {mock && <Chip label="Dane przykładowe" size="small" color="warning" />}
                </Box>
                {[directionText(suggested), distanceText(suggested)].filter(Boolean).length > 0 && (
                  <Typography variant="body2" color="text.secondary" noWrap>
                    {[directionText(suggested), distanceText(suggested)].filter(Boolean).join(' · ')}
                  </Typography>
                )}
              </Box>
            </Box>
          )}

          <Button fullWidth variant="contained" size="large" disabled={!selected} onClick={onConfirm} sx={{ mt: 1.5 }}>
            {selected ? `Jadę tą linią: ${vehicleName(selected)}` : 'Jadę tą linią'}
          </Button>
          {!full && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 0.75 }}>
              Przesuń w górę, by zobaczyć inne linie
            </Typography>
          )}

          {/* more options: visible when the popup is pulled up (inert, so they cannot be focused while clipped) */}
          <Box {...(full ? {} : ({ inert: '' } as object))}>
          {others.length > 0 && (
            <>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2, mb: 0.75, ml: 0.5 }}>
                Inne możliwości
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${others.length}, 1fr)`, gap: 1 }}>
                {others.map((c) => (
                  <Box
                    key={c.id}
                    {...pressable(c)}
                    sx={[
                      { p: 1.25, borderRadius: RADIUS.tile, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5, textAlign: 'center', minWidth: 0 },
                      cardSx(c.id === selectedId),
                    ]}
                  >
                    <ModeBadge vehicle={c} size={40} />
                    <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                      {vehicleName(c)}
                    </Typography>
                    {directionText(c) && (
                      <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.2 }}>
                        {directionText(c)}
                      </Typography>
                    )}
                  </Box>
                ))}
              </Box>
            </>
          )}

          <Autocomplete
            size="small"
            options={lines}
            value={null}
            blurOnSelect
            disabled={lines.length === 0}
            noOptionsText="Brak takiej linii"
            onChange={(_, line) => line && onManualLine(line)}
            renderInput={(params) => <TextField {...params} label="Inna linia" placeholder="Wpisz numer linii" />}
            sx={{ mt: 1.5 }}
          />
          {manual && (
            <Box
              {...pressable(manual)}
              sx={[
                { display: 'flex', alignItems: 'center', gap: 1.5, p: 1.25, mt: 1, borderRadius: RADIUS.tile },
                cardSx(manual.id === selectedId),
              ]}
            >
              <ModeBadge vehicle={manual} size={40} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontWeight: 700, lineHeight: 1.2 }}>{vehicleName(manual)}</Typography>
                <Typography variant="caption" color="text.secondary">
                  wybrana ręcznie
                </Typography>
              </Box>
              <IconButton
                size="small"
                aria-label="Usuń ręcznie wybraną linię"
                onClick={(e) => {
                  e.stopPropagation();
                  onClearManual();
                }}
              >
                <Close fontSize="small" />
              </IconButton>
            </Box>
          )}

          <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
            <Button size="small" startIcon={<Refresh />} disabled={loading} onClick={onRedetect} sx={{ flex: 1 }}>
              {loading ? 'Szukam…' : 'Wykryj ponownie'}
            </Button>
            <Button size="small" color="inherit" onClick={onDismiss} sx={{ flex: 1 }}>
              Nie jadę komunikacją
            </Button>
          </Box>
          </Box>
        </Box>
      )}
    </Paper>
  );
}
