import {
  alpha,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
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
import { RADIUS } from '../layout';
import SnapSheet, { type SheetSnap } from './SnapSheet';
import { formatDistance } from '../utils/format';
import { pressableProps } from './pressable';

const vehicleName = (v: VehicleCandidate) => `${MODE_META[v.mode].label} ${v.line}`;
/** "kier. X", or nothing when the direction is unknown (live buses have none yet). */
const directionText = (v: VehicleCandidate) => (v.direction ? `kier. ${v.direction}` : '');
/** Distance of the vehicle from the user, when the backend sent it. */
const distanceText = (v: VehicleCandidate) =>
  v.distanceM !== undefined ? `ok. ${formatDistance(v.distanceM)} od Ciebie` : '';

/** Heights the popup settles on: a bar, the middle (suggested vehicle + confirm) and the full popup. */
export type VehicleSnap = SheetSnap;

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
  /** The backend could not be reached, so nothing was detected. */
  offline?: boolean;
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
  offline = false,
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
    <SnapSheet
      snap={snap}
      onSnapChange={onSnapChange}
      middleHeight={258}
      ariaLabel="Okienko pojazdu"
      header={({ barLike, full }) => (
        <>
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
                <Typography sx={{ flex: 1 }}>{offline ? 'Nie połączono z serwerem' : 'Nie wykryto pojazdu'}</Typography>
                <ExpandLess color="action" />
              </>
            )}
          </Box>
        )}
        </>
      )}
    >
      {({ full }) => (
        <>
          {/* primary block: visible in the middle height */}
          {loading && candidates.length === 0 && (
            <Box sx={{ display: 'grid', placeItems: 'center', py: 3 }}>
              <CircularProgress size={32} />
            </Box>
          )}

          {offline && !loading && candidates.length === 0 && (
            <Box sx={{ py: 2, textAlign: 'center' }}>
              <Typography color="text.secondary">Nie połączono z serwerem, więc nie wykryję pojazdu.</Typography>
              <Button onClick={onRedetect} sx={{ mt: 1 }}>
                Spróbuj ponownie
              </Button>
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
        </>
      )}
    </SnapSheet>
  );
}
