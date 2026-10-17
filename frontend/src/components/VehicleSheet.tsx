import { useRef, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { alpha, Box, Button, Chip, CircularProgress, Collapse, Paper, Typography, useTheme, type Theme } from '@mui/material';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import { MODE_META, modeColor } from '../modes';
import type { VehicleCandidate } from '../types';

const vehicleName = (v: VehicleCandidate) => `${MODE_META[v.mode].label} ${v.line}`;

/** Tap, swipe down or swipe up on an element. */
function useSwipe(onTap: () => void, onUp: () => void, onDown: () => void) {
  const startY = useRef<number | null>(null);
  return {
    onPointerDown: (e: ReactPointerEvent<HTMLElement>) => {
      startY.current = e.clientY;
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        /* pointer is not active (e.g. synthetic event): the swipe still works */
      }
    },
    onPointerUp: (e: ReactPointerEvent<HTMLElement>) => {
      if (startY.current === null) return;
      const dy = e.clientY - startY.current;
      startY.current = null;
      if (dy > 40) onDown();
      else if (dy < -40) onUp();
      else if (Math.abs(dy) < 10) onTap();
    },
    onPointerCancel: () => {
      startY.current = null;
    },
  };
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
  loading: boolean;
  open: boolean;
  selectedId: string | null;
  /** The vehicle the user confirmed (shown in the hidden bar). */
  confirmed: VehicleCandidate | null;
  onOpenChange: (open: boolean) => void;
  onSelect: (id: string) => void;
  onConfirm: () => void;
  /** "I am not in a vehicle". */
  onDismiss: () => void;
}

/**
 * "Which vehicle am I in?" window. Open from the start; swipe down (or tap the handle) to hide it
 * into a bar, swipe up (or tap the bar) to bring it back. Coloured by the theme, so it follows the map look.
 */
export default function VehicleSheet({
  candidates,
  loading,
  open,
  selectedId,
  confirmed,
  onOpenChange,
  onSelect,
  onConfirm,
  onDismiss,
}: Props) {
  const swipe = useSwipe(
    () => onOpenChange(!open),
    () => onOpenChange(true),
    () => onOpenChange(false),
  );

  const suggested = candidates[0];
  const others = candidates.slice(1, 4);
  const selected = candidates.find((c) => c.id === selectedId) ?? null;
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
  const pressable = (c: VehicleCandidate) => ({
    role: 'button',
    tabIndex: 0,
    'aria-pressed': c.id === selectedId,
    onClick: () => onSelect(c.id),
    onKeyDown: (e: ReactKeyboardEvent) => (e.key === 'Enter' || e.key === ' ') && onSelect(c.id),
  });

  return (
    <Paper
      elevation={8}
      sx={{
        position: 'absolute',
        zIndex: 1000,
        bottom: 'calc(env(safe-area-inset-bottom) + 20px)',
        left: { xs: 8, sm: 16 },
        right: { xs: 8, sm: 'auto' },
        width: { sm: 440 },
        maxHeight: { xs: '62vh', sm: 'calc(100vh - 200px)' },
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '28px',
        overflow: 'hidden',
      }}
    >
      {/* drag zone: handle + header (tap toggles, swipe hides / shows) */}
      <Box
        {...swipe}
        role="button"
        aria-label={open ? 'Schowaj okienko pojazdu' : 'Pokaż okienko pojazdu'}
        aria-expanded={open}
        sx={{ touchAction: 'none', cursor: 'grab', userSelect: 'none', px: 2.5, pb: open ? 1 : 1.5 }}
      >
        <Box sx={{ display: 'grid', placeItems: 'center', py: 1.25 }}>
          <Box sx={{ width: 36, height: 4, borderRadius: 2, bgcolor: 'text.disabled', opacity: 0.5 }} />
        </Box>

        {open ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.25 }}>
                W jakim pojeździe jesteś?
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Sugerujemy na podstawie lokalizacji. Wybierz właściwą linię.
              </Typography>
            </Box>
            <ExpandMore color="action" />
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
                  <Typography variant="body2" color="text.secondary" noWrap>
                    kier. {shown.direction}
                  </Typography>
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

      <Collapse in={open} unmountOnExit>
        <Box sx={{ overflowY: 'auto', px: 2, pb: 2, maxHeight: { xs: 'calc(62vh - 90px)', sm: 'none' } }}>
          {loading && candidates.length === 0 && (
            <Box sx={{ display: 'grid', placeItems: 'center', py: 4 }}>
              <CircularProgress size={32} />
            </Box>
          )}

          {suggested && (
            <Box
              {...pressable(suggested)}
              sx={[{ display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, borderRadius: 4 }, cardSx(suggested.id === selectedId)]}
            >
              <ModeBadge vehicle={suggested} size={52} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                    {vehicleName(suggested)}
                  </Typography>
                  <Chip label="Sugerowana" size="small" color="secondary" variant="outlined" />
                </Box>
                <Typography variant="body2" color="text.secondary" noWrap>
                  kier. {suggested.direction}
                </Typography>
              </Box>
            </Box>
          )}

          {others.length > 0 && (
            <>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5, mb: 0.75, ml: 0.5 }}>
                Inne możliwości
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${others.length}, 1fr)`, gap: 1 }}>
                {others.map((c) => (
                  <Box
                    key={c.id}
                    {...pressable(c)}
                    sx={[
                      { p: 1.25, borderRadius: 3.5, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5, textAlign: 'center', minWidth: 0 },
                      cardSx(c.id === selectedId),
                    ]}
                  >
                    <ModeBadge vehicle={c} size={40} />
                    <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                      {vehicleName(c)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.2 }}>
                      kier. {c.direction}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </>
          )}

          <Button
            fullWidth
            variant="contained"
            size="large"
            disabled={!selected}
            onClick={onConfirm}
            sx={{ mt: 2 }}
          >
            {selected ? `Jadę tą linią: ${vehicleName(selected)}` : 'Jadę tą linią'}
          </Button>
          <Button fullWidth color="inherit" onClick={onDismiss} sx={{ mt: 0.5 }}>
            Nie jadę komunikacją
          </Button>
        </Box>
      </Collapse>
    </Paper>
  );
}
