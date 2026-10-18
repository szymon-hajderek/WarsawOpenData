import { useState } from 'react';
import { Box, Button, Chip, Popover, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import Schedule from '@mui/icons-material/Schedule';
import { RADIUS } from '../layout';
import {
  dateKey,
  departureLabel,
  isPastDeparture,
  makeDeparture,
  nextDay,
  timeKey,
  type Departure,
} from '../utils/departure';

interface Props {
  value: Departure;
  onChange: (d: Departure) => void;
}

/** "Wyjazd: Teraz" chip; a tap opens a small picker (today / tomorrow / a date + a time, or back to now). */
export default function DepartureControl({ value, onChange }: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const now = new Date();
  const today = dateKey(now);
  const tomorrow = dateKey(nextDay(now));
  const past = isPastDeparture(value, now);

  const open = (el: HTMLElement) => {
    // the picker starts at the chosen departure, or at the current time
    const [d, t] = value ? value.split('T') : [today, timeKey(now)];
    setDate(d);
    setTime(t);
    setAnchor(el);
  };
  const close = () => setAnchor(null);
  const apply = () => {
    if (date && time) onChange(makeDeparture(date, time));
    close();
  };
  const reset = () => {
    onChange(null);
    close();
  };

  const day = date === today ? 'today' : date === tomorrow ? 'tomorrow' : null;

  return (
    <>
      <Chip
        icon={<Schedule />}
        label={departureLabel(value, now)}
        size="small"
        clickable
        variant={value ? 'filled' : 'outlined'}
        color={value && !past ? 'primary' : 'default'}
        aria-haspopup="dialog"
        title={past ? 'Ta godzina już minęła' : undefined}
        onClick={(e) => open(e.currentTarget)}
        sx={past ? { color: 'text.disabled', '& .MuiChip-icon': { color: 'text.disabled' } } : undefined}
      />
      <Popover
        open={anchor !== null}
        anchorEl={anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{ paper: { sx: { borderRadius: RADIUS.card, p: 2, width: 280 } } }}
      >
        <Box role="dialog" aria-label="Godzina wyjazdu" sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            Godzina wyjazdu
          </Typography>
          <ToggleButtonGroup
            exclusive
            size="small"
            fullWidth
            value={day}
            aria-label="Dzień wyjazdu"
            onChange={(_, v: 'today' | 'tomorrow' | null) => v && setDate(v === 'today' ? today : tomorrow)}
            sx={{ '& .MuiToggleButton-root': { py: 0.25 } }}
          >
            <ToggleButton value="today">Dziś</ToggleButton>
            <ToggleButton value="tomorrow">Jutro</ToggleButton>
          </ToggleButtonGroup>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              type="date"
              label="Data"
              size="small"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ flex: 1.4, '& .MuiOutlinedInput-root': { borderRadius: RADIUS.control } }}
            />
            <TextField
              type="time"
              label="Godzina"
              size="small"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              sx={{ flex: 1, '& .MuiOutlinedInput-root': { borderRadius: RADIUS.control } }}
            />
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button size="small" onClick={reset}>
              Teraz
            </Button>
            <Button size="small" variant="contained" onClick={apply} disabled={!date || !time}>
              Gotowe
            </Button>
          </Box>
        </Box>
      </Popover>
    </>
  );
}
