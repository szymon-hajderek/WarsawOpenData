import { Alert, alpha, Box, Button, Chip, Typography, useTheme } from '@mui/material';
import DirectionsBus from '@mui/icons-material/DirectionsBus';
import Place from '@mui/icons-material/Place';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import SnapSheet, { type SheetSnap } from './SnapSheet';
import { instruction } from './RouteDetailsSheet';
import { MODE_META, modeColor } from '../modes';
import { formatDistance, formatDuration } from '../utils/format';
import { nextStepText, type TripProgress } from '../utils/progress';
import type { RouteOption, VehicleCandidate } from '../types';
import { RADIUS } from '../layout';

interface Props {
  route: RouteOption;
  /** Null until the first position is known. */
  progress: TripProgress | null;
  /** Seconds since "Rozpocznij przejazd" (from the recorder). */
  elapsedS: number;
  /** The vehicle the user confirmed ("Jadę tą linią"), kept independently of the destination. */
  vehicle: VehicleCandidate | null;
  snap: SheetSnap;
  onSnapChange: (snap: SheetSnap) => void;
  /** "W jakim pojeździe jestem?" */
  onDetectVehicle: () => void;
  /** "Zmień cel": the full search card, the start = the vehicle or the GPS position. */
  onChangeDestination: () => void;
  /** "Zmień trasę" (off the route): the same search with the current destination. */
  onReroute: () => void;
  /** "Zakończ": leaves the active trip and saves the pace recording. */
  onEnd: () => void;
  /** Waiting for a later departure: "Wyjazd o 14:30 · za 23 min" (null = the trip runs). */
  waiting?: { departure: string; countdown: string } | null;
  /** "Ruszam teraz": start the trip before its departure time (same route). */
  onStartNow?: () => void;
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

/** The active trip: the next step, the current leg highlighted, and the ways to change or end the trip. */
export default function ActiveTripSheet({
  route,
  progress,
  elapsedS,
  vehicle,
  snap,
  onSnapChange,
  onDetectVehicle,
  onChangeDestination,
  onReroute,
  onEnd,
  waiting = null,
  onStartNow,
}: Props) {
  const palette = useTheme().palette.mode;
  const current = waiting ? 0 : progress?.legIndex ?? 0;
  const nextStep = (!waiting && progress?.nextStep) || nextStepText(route.legs, 0) || instruction(route.legs[0]);

  return (
    <SnapSheet
      snap={snap}
      onSnapChange={onSnapChange}
      middleHeight={300}
      ariaLabel="Aktywny przejazd"
      header={({ barLike, full }) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" noWrap component="div">
              {waiting ? `Wyjazd o ${waiting.departure} · ${waiting.countdown}` : `Aktywny przejazd · ${clock(elapsedS)} · cel o ${route.arrival}`}
            </Typography>
            <Typography variant="h6" noWrap sx={{ fontWeight: 700, lineHeight: 1.25 }} data-testid="next-step">
              {nextStep}
            </Typography>
          </Box>
          {barLike || !full ? <ExpandLess color="action" /> : <ExpandMore color="action" />}
        </Box>
      )}
      footer={
        waiting ? (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button variant="outlined" onClick={onEnd} sx={{ flex: 1 }}>
              Anuluj
            </Button>
            <Button variant="contained" onClick={onStartNow} sx={{ flex: 1 }}>
              Ruszam teraz
            </Button>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button variant="outlined" startIcon={<Place />} onClick={onChangeDestination} sx={{ flex: 1 }}>
              Zmień cel
            </Button>
            <Button variant="contained" onClick={onEnd} sx={{ flex: 1 }}>
              Zakończ
            </Button>
          </Box>
        )
      }
    >
      <Box>
        {!waiting && progress?.offRoute && (
          <Alert
            severity="warning"
            sx={{ mb: 1.5 }}
            action={
              <Button color="inherit" size="small" onClick={onReroute}>
                Zmień trasę
              </Button>
            }
          >
            Zboczyłeś z trasy
          </Alert>
        )}

        <Box sx={{ display: waiting ? 'none' : 'flex', alignItems: 'center', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
          <Button size="small" variant="outlined" startIcon={<DirectionsBus />} onClick={onDetectVehicle}>
            W jakim pojeździe jestem?
          </Button>
          {vehicle && (
            <Chip
              size="small"
              color="secondary"
              label={`Jedziesz: ${MODE_META[vehicle.mode].label} ${vehicle.line}${vehicle.direction ? ` → ${vehicle.direction}` : ''}`}
            />
          )}
        </Box>

        <Box component="ol" sx={{ listStyle: 'none', p: 0, m: 0, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          {route.legs.map((leg, i) => {
            const Icon = MODE_META[leg.mode].icon;
            const color = modeColor(leg.mode, palette);
            const isCurrent = i === current;
            return (
              <Box
                component="li"
                key={`${i}-${leg.mode}`}
                aria-current={isCurrent ? 'step' : undefined}
                sx={(t) => ({
                  display: 'flex',
                  gap: 1.25,
                  alignItems: 'center',
                  p: 1,
                  borderRadius: RADIUS.tile,
                  opacity: i < current ? 0.5 : 1,
                  border: 2,
                  borderColor: isCurrent ? 'primary.main' : 'transparent',
                  bgcolor: isCurrent ? alpha(t.palette.primary.main, 0.1) : 'transparent',
                })}
              >
                <Box sx={{ width: 32, height: 32, borderRadius: '50%', display: 'grid', placeItems: 'center', bgcolor: alpha(color, 0.18), color, flexShrink: 0 }}>
                  <Icon sx={{ fontSize: 18 }} />
                </Box>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: isCurrent ? 700 : 500 }}>
                    {instruction(leg)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatDuration(leg.durationMin)} · {formatDistance(leg.distanceM)}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Box>
      </Box>
    </SnapSheet>
  );
}
