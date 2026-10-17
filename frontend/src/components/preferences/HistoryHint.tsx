import { alpha, Box, Button, FormControlLabel, Switch, Typography } from '@mui/material';
import { formatKmh } from '../../preferences/model';
import { RADIUS } from '../../layout';
import { MIN_TRIPS, type ModeSummary } from '../../history/types';

/** "1 przejazd", "2 przejazdy", "5 przejazdów". */
export function tripsLabel(n: number): string {
  if (n === 1) return '1 przejazd';
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) return `${n} przejazdy`;
  return `${n} przejazdów`;
}

export interface HistoryInfo {
  summary: ModeSummary;
  /** Speed taken from the history right now (switch on and enough trips), else null. */
  used: number | null;
}

interface Props extends HistoryInfo {
  /** The speed the settings give right now (level or typed speed). */
  currentKmh: number;
  range: readonly [number, number];
  autoSpeed: boolean;
  onAutoChange: (on: boolean) => void;
  /** Sets the average as the typed speed. */
  onUse: (kmh: number) => void;
}

/** Suggestion to use the average speed from the user's own trips, and the switch to always use it. */
export default function HistoryHint({ summary, used, currentKmh, range, autoSpeed, onAutoChange, onUse }: Props) {
  const avg = summary.avgKmh;
  const differs = avg !== null && Math.abs(avg - currentKmh) / currentKmh >= 0.1;
  const suggest = summary.enough && avg !== null && differs && !autoSpeed;
  const clamped = avg === null ? 0 : Math.min(range[1], Math.max(range[0], avg));

  return (
    <Box sx={(t) => ({ mt: 1.5, p: 1.5, borderRadius: RADIUS.control, bgcolor: alpha(t.palette.secondary.main, 0.1) })}>
      <Typography variant="body2" sx={{ fontWeight: 700 }}>
        Twoja średnia z historii
      </Typography>
      {summary.trips === 0 ? (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          Jeszcze nie ma przejazdów. Zapisz je w widoku trasy przyciskiem „Rozpocznij przejazd”.
        </Typography>
      ) : (
        <Typography variant="body2">
          {avg !== null ? formatKmh(avg) : '—'} · {tripsLabel(summary.trips)}
          {!summary.enough && (
            <Typography component="span" variant="caption" color="text.secondary">
              {' '}
              (potrzeba co najmniej {MIN_TRIPS})
            </Typography>
          )}
        </Typography>
      )}

      {suggest && (
        <Button size="small" variant="outlined" color="secondary" sx={{ mt: 0.75 }} onClick={() => onUse(Math.round(clamped * 10) / 10)}>
          Użyj {formatKmh(Math.round(clamped * 10) / 10)}
        </Button>
      )}

      <FormControlLabel
        sx={{ display: 'flex', mt: 0.5, mr: 0 }}
        control={<Switch size="small" checked={autoSpeed} onChange={(e) => onAutoChange(e.target.checked)} />}
        label={<Typography variant="body2">Zawsze używaj średniej z historii</Typography>}
      />
      {autoSpeed && used !== null && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          Używana prędkość: {formatKmh(used)} (średnia z {tripsLabel(summary.trips)}).
        </Typography>
      )}
      {autoSpeed && used === null && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          Na razie za mało przejazdów, więc obowiązuje ustawione tempo.
        </Typography>
      )}
    </Box>
  );
}
