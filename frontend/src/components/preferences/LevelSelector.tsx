import { useEffect, useState } from 'react';
import { alpha, Box, Button, Collapse, InputAdornment, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { formatKmh, type LevelDef } from '../../preferences/model';
import { RADIUS } from '../../layout';

interface Props<L extends string> {
  levels: LevelDef<L>[];
  level: L;
  /** Average speed typed by the user; replaces the level when set. */
  customKmh: number | null;
  range: readonly [number, number];
  onChange: (level: L, customKmh: number | null) => void;
  ariaLabel: string;
}

const parse = (text: string) => parseFloat(text.replace(',', '.'));

/** Level of advancement (buttons) with an "advanced" option to type the average speed instead. */
export default function LevelSelector<L extends string>({ levels, level, customKmh, range, onChange, ariaLabel }: Props<L>) {
  const [advanced, setAdvanced] = useState(customKmh !== null);
  const [text, setText] = useState(customKmh === null ? '' : String(customKmh));

  const value = parse(text);
  const invalid = text !== '' && (Number.isNaN(value) || value < range[0] || value > range[1]);

  // Keep the text in sync when the value changes from outside (e.g. "restore defaults").
  useEffect(() => {
    const typed = parse(text);
    if (customKmh === null ? text !== '' && !invalid : typed !== customKmh) {
      setText(customKmh === null ? '' : String(customKmh));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customKmh]);

  const onText = (next: string) => {
    setText(next);
    const v = parse(next);
    if (next === '') onChange(level, null);
    else if (!Number.isNaN(v) && v >= range[0] && v <= range[1]) onChange(level, Math.round(v * 10) / 10);
  };

  return (
    <Box>
      <ToggleButtonGroup
        exclusive
        fullWidth
        size="small"
        aria-label={ariaLabel}
        value={customKmh !== null ? null : level}
        onChange={(_, v: L | null) => {
          if (!v) return;
          setText('');
          onChange(v, null);
        }}
        sx={{
          '& .MuiToggleButton-root': { flexDirection: 'column', textTransform: 'none', py: 1, lineHeight: 1.2 },
          '& .Mui-selected': { fontWeight: 700 },
        }}
      >
        {levels.map((l) => (
          <ToggleButton key={l.id} value={l.id}>
            <span>{l.label}</span>
            <Typography variant="caption" color="text.secondary">
              {formatKmh(l.kmh)}
            </Typography>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      <Button size="small" color="inherit" onClick={() => setAdvanced((a) => !a)} sx={{ mt: 0.5, px: 1, opacity: 0.8 }}>
        {advanced ? 'Ukryj zaawansowane' : 'Zaawansowane: wpisz średnią prędkość'}
      </Button>
      <Collapse in={advanced}>
        <Box
          sx={(t) => ({ mt: 0.5, p: 1.5, borderRadius: RADIUS.control, bgcolor: alpha(t.palette.primary.main, 0.06) })}
        >
          <TextField
            fullWidth
            size="small"
            label="Średnia prędkość"
            value={text}
            onChange={(e) => onText(e.target.value)}
            error={invalid}
            helperText={
              invalid
                ? `Wpisz liczbę od ${range[0]} do ${range[1]} km/h`
                : customKmh !== null
                  ? 'Ta wartość zastępuje poziom powyżej.'
                  : `Od ${range[0]} do ${range[1]} km/h. Zostaw puste, żeby użyć poziomu.`
            }
            slotProps={{
              htmlInput: { inputMode: 'decimal', 'aria-label': `${ariaLabel}: średnia prędkość w km/h` },
              input: { endAdornment: <InputAdornment position="end">km/h</InputAdornment> },
            }}
          />
        </Box>
      </Collapse>
    </Box>
  );
}
