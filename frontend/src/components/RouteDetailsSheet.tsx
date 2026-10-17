import { Fragment } from 'react';
import { Alert, alpha, Box, Button, Chip, CircularProgress, Collapse, IconButton, Paper, Typography, useTheme } from '@mui/material';
import FiberManualRecord from '@mui/icons-material/FiberManualRecord';
import ArrowBack from '@mui/icons-material/ArrowBack';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import Sheet from './Sheet';
import LegChain from './LegChain';
import { MODE_META, modeColor } from '../modes';
import { useHistory } from '../history/HistoryProvider';
import { usePreferences } from '../preferences/PreferencesProvider';
import { formatCost, formatDistance, formatDuration, stopsLabel, transfersLabel } from '../utils/format';
import type { Place, RouteLeg, RouteOption } from '../types';
import { RADIUS } from '../layout';

function instruction(leg: RouteLeg): string {
  const dist = formatDistance(leg.distanceM);
  switch (leg.mode) {
    case 'walk':
      return `Przejdź ${dist} do: ${leg.to}`;
    case 'bike':
      return `Jedź rowerem Veturilo ${dist} do: ${leg.to}`;
    default:
      return `${MODE_META[leg.mode].label} ${leg.line ?? ''} do: ${leg.to}`.replace('  ', ' ');
  }
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={(t) => ({ p: 1.5, borderRadius: RADIUS.tile, bgcolor: alpha(t.palette.primary.main, 0.08) })}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700 }}>{value}</Typography>
    </Box>
  );
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

/** Records the ride with GPS so the app can learn the user's real pace (see `src/history/`). */
function TripRecorder({ route }: { route: RouteOption }) {
  const { tracker } = useHistory();
  const { effective } = usePreferences();
  const walkAs = effective.wheelchair.type !== 'none' ? 'wheelchair' : 'walking';
  const legs = route.legs.map((l) => ({ mode: l.mode, distanceM: l.distanceM }));
  const { status } = tracker;

  return (
    <Box sx={{ mt: 2 }}>
      {status === 'tracking' ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Chip
            icon={<FiberManualRecord sx={{ fontSize: 14 }} />}
            color="error"
            label={`Zapisuję przejazd · ${clock(tracker.elapsedS)}`}
            sx={{ flex: 1, justifyContent: 'flex-start' }}
          />
          <Button variant="contained" onClick={() => void tracker.stop()}>
            Zakończ
          </Button>
        </Box>
      ) : status === 'saving' ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <CircularProgress size={20} />
          <Typography variant="body2">Zapisuję przejazd…</Typography>
        </Box>
      ) : (
        <>
          <Button
            fullWidth
            variant="outlined"
            startIcon={<FiberManualRecord sx={{ color: 'error.main' }} />}
            onClick={() => tracker.start(legs, walkAs)}
          >
            Rozpocznij przejazd
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75, textAlign: 'center' }}>
            Zapiszemy Twoje tempo i podpowiemy średnią prędkość w Preferencjach.
          </Typography>
        </>
      )}
      {tracker.message && status !== 'tracking' && status !== 'saving' && (
        <Alert
          severity={status === 'error' ? 'error' : 'success'}
          sx={{ mt: 1.5 }}
          onClose={tracker.dismiss}
          action={
            status === 'error' && tracker.message.includes('serwerem') ? (
              <Button color="inherit" size="small" onClick={() => void tracker.retry()}>
                Ponów
              </Button>
            ) : undefined
          }
        >
          {tracker.message}
        </Alert>
      )}
    </Box>
  );
}

interface Props {
  route: RouteOption;
  origin: Place;
  destination: Place;
  /** Whether the list of steps is expanded (the parent adjusts the map padding to it). */
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  onBack: () => void;
}

/** The chosen route: a header at the top and a summary + steps panel at the bottom. */
export default function RouteDetailsSheet({
  route,
  origin,
  destination,
  expanded,
  onExpandedChange,
  onBack,
}: Props) {
  const theme = useTheme();
  const palette = theme.palette.mode;

  // The longest leg sets the icon of the whole route
  const mainLeg = route.legs.reduce((a, b) => (b.durationMin > a.durationMin ? b : a), route.legs[0]);
  const MainIcon = MODE_META[mainLeg.mode].icon;
  // intermediate stops: waypoints without the start and the destination
  const stopCount = Math.max(0, (route.waypoints?.length ?? 0) - 2);

  return (
    <>
      <Box
        sx={{
          position: 'absolute',
          zIndex: 1000,
          top: 'calc(env(safe-area-inset-top) + 12px)',
          left: { xs: 12, sm: 16 },
          right: { xs: 12, sm: 'auto' },
          width: { sm: 440 },
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <IconButton
          aria-label="Wróć do wyboru trasy"
          onClick={onBack}
          sx={{ bgcolor: 'background.paper', boxShadow: 4, '&:hover': { bgcolor: 'background.paper' } }}
        >
          <ArrowBack />
        </IconButton>
        <Paper elevation={4} sx={{ flex: 1, minWidth: 0, px: 2.5, py: 1, borderRadius: RADIUS.pill }}>
          <Typography noWrap sx={{ fontWeight: 700 }}>
            {route.title}
          </Typography>
          <Typography variant="body2" color="text.secondary" noWrap>
            {route.departure} – {route.arrival} · {transfersLabel(route.transfers)}
            {stopCount > 0 && ` · ${stopsLabel(stopCount)}`}
          </Typography>
        </Paper>
      </Box>

      <Sheet onHandleClick={() => onExpandedChange(!expanded)} maxHeight={{ xs: '52vh', sm: 'calc(100vh - 120px)' }}>
        <Box sx={{ overflowY: 'auto', px: 2, pb: 2 }}>
          {/* start -> finish */}
          <Box sx={{ display: 'flex', alignItems: 'stretch', position: 'relative', gap: 1 }}>
            <Box sx={(t) => ({ flex: 1, minWidth: 0, p: 1.5, borderRadius: RADIUS.tile, bgcolor: alpha(t.palette.primary.main, 0.08), pr: 4 })}>
              <Typography variant="caption" color="text.secondary">
                Start · {route.departure}
              </Typography>
              <Typography noWrap sx={{ fontWeight: 700 }}>
                {origin.label}
              </Typography>
            </Box>
            <Box sx={(t) => ({ flex: 1, minWidth: 0, p: 1.5, borderRadius: RADIUS.tile, bgcolor: alpha(t.palette.primary.main, 0.08), textAlign: 'right', pl: 4 })}>
              <Typography variant="caption" color="text.secondary">
                Cel · {route.arrival}
              </Typography>
              <Typography noWrap sx={{ fontWeight: 700 }}>
                {destination.label}
              </Typography>
            </Box>
            <Box
              sx={(t) => ({
                position: 'absolute',
                left: '50%',
                top: '50%',
                transform: 'translate(-50%, -50%)',
                width: 48,
                height: 48,
                borderRadius: '50%',
                display: 'grid',
                placeItems: 'center',
                color: t.palette.primary.contrastText,
                background: `linear-gradient(135deg, ${t.palette.primary.main}, ${t.palette.secondary.main})`,
                border: `4px solid ${t.palette.background.paper}`,
              })}
            >
              <MainIcon />
            </Box>
          </Box>

          {/* leg proportions */}
          <Box sx={{ display: 'flex', gap: '3px', mt: 2, height: 10 }}>
            {route.legs.map((leg, i) => (
              <Box
                key={`${i}-${leg.mode}`}
                sx={{
                  flex: leg.durationMin,
                  borderRadius: RADIUS.pill,
                  bgcolor: modeColor(leg.mode, palette),
                  opacity: leg.mode === 'walk' ? 0.55 : 1,
                }}
              />
            ))}
          </Box>
          <Box sx={{ mt: 1 }}>
            <LegChain legs={route.legs} />
          </Box>

          {/* stats */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mt: 2 }}>
            <Tile label="Czas" value={formatDuration(route.durationMin)} />
            <Tile label="Dystans" value={formatDistance(route.distanceM)} />
            <Tile label="Spalone kalorie" value={`${route.calories} kcal`} />
            <Tile label="Koszt (szac.)" value={`${route.costPln > 0 ? '~' : ''}${formatCost(route.costPln)}`} />
          </Box>

          <TripRecorder route={route} />

          {/* steps */}
          <Button
            fullWidth
            color="inherit"
            aria-expanded={expanded}
            onClick={() => onExpandedChange(!expanded)}
            endIcon={expanded ? <ExpandLess /> : <ExpandMore />}
            sx={{ mt: 1.5, justifyContent: 'space-between', fontWeight: 700 }}
          >
            Przebieg trasy
          </Button>
          <Collapse in={expanded}>
            <Box sx={{ height: 8 }} />
            {route.legs.map((leg, i) => {
              const color = modeColor(leg.mode, palette);
              const Icon = MODE_META[leg.mode].icon;
              const last = i === route.legs.length - 1;
              const stopPlace = leg.stop ? route.waypoints?.[leg.stop] : undefined;
              return (
                <Fragment key={`${i}-${leg.mode}`}>
                <Box sx={{ display: 'flex', gap: 1.5 }}>
                  <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <Box
                      sx={{
                        width: 36,
                        height: 36,
                        borderRadius: '50%',
                        display: 'grid',
                        placeItems: 'center',
                        bgcolor: alpha(color, 0.18),
                        color,
                      }}
                    >
                      <Icon sx={{ fontSize: 20 }} />
                    </Box>
                    {!last && <Box sx={{ flex: 1, width: 2, my: 0.5, bgcolor: 'divider', minHeight: 12 }} />}
                  </Box>
                  <Box sx={{ pb: last ? 0 : 1.5, pt: 0.25 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {instruction(leg)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDuration(leg.durationMin)} · {formatDistance(leg.distanceM)}
                    </Typography>
                  </Box>
                </Box>
                {leg.stop && (
                  <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'stretch' }}>
                    <Box sx={{ width: 36, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <Box
                        sx={(t) => ({
                          width: 26,
                          height: 26,
                          borderRadius: '50%',
                          display: 'grid',
                          placeItems: 'center',
                          fontSize: 13,
                          fontWeight: 700,
                          bgcolor: t.palette.primary.main,
                          color: t.palette.primary.contrastText,
                        })}
                      >
                        {leg.stop}
                      </Box>
                      <Box sx={{ flex: 1, width: 2, my: 0.5, bgcolor: 'divider', minHeight: 12 }} />
                    </Box>
                    <Box sx={{ pb: 1.5, pt: 0.25 }}>
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>
                        Przystanek {leg.stop}: {stopPlace?.label ?? leg.to}
                      </Typography>
                    </Box>
                  </Box>
                )}
                </Fragment>
              );
            })}
          </Collapse>
        </Box>
      </Sheet>
    </>
  );
}
