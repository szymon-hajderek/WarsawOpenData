import { useState } from 'react';
import {
  Box,
  Button,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { CyclingSection, TransferChips, TransportModesSection, WalkingSection, WheelchairSection } from './PreferenceFields';
import AreaPicker from './AreaPicker';
import { DAY_LABELS, type PreferenceOverrides, type Preferences, type TimeRule } from '../../preferences/model';

interface Props {
  /** The rule to edit, or null for a new one. */
  rule: TimeRule | null;
  /** Base preferences: the starting values of every overridden section. */
  base: Preferences;
  onSave: (rule: TimeRule) => void;
  onClose: () => void;
}

const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];

/** Add / edit a time rule: hours, days and the preferences that change in that time. Mount it only while open. */
export default function RuleDialog({ rule, base, onSave, onClose }: Props) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));

  const [name, setName] = useState(rule?.name ?? '');
  const [days, setDays] = useState<number[]>(rule?.days ?? ALL_DAYS);
  const [from, setFrom] = useState(rule?.from ?? '22:00');
  const [to, setTo] = useState(rule?.to ?? '06:00');
  const [o, setO] = useState<PreferenceOverrides>(rule?.overrides ?? {});

  const hasMaxTransfers = 'maxTransfers' in o;
  const toggle = (key: keyof PreferenceOverrides, on: boolean) =>
    setO((prev) => {
      const next = { ...prev };
      if (!on) delete next[key];
      else if (key === 'maxTransfers') next.maxTransfers = base.priorities.maxTransfers;
      else if (key === 'excluded') next.excluded = base.priorities.excluded;
      else if (key === 'excludedModes') next.excludedModes = base.excludedModes;
      else (next as Record<string, unknown>)[key] = base[key];
      return next;
    });

  const hasOverride = Object.keys(o).length > 0;
  const valid = days.length > 0 && from !== '' && to !== '' && hasOverride;

  const save = () =>
    onSave({
      id: rule?.id ?? `rule-${Date.now()}`,
      name: name.trim() || 'Reguła',
      days: [...days].sort(),
      from,
      to,
      overrides: o,
    });

  const switchRow = (key: keyof PreferenceOverrides, label: string, on: boolean) => (
    <FormControlLabel
      control={<Switch checked={on} onChange={(e) => toggle(key, e.target.checked)} />}
      label={label}
      sx={{ fontWeight: 600 }}
    />
  );

  return (
    <Dialog open fullScreen={fullScreen} fullWidth maxWidth="sm" onClose={onClose} aria-labelledby="rule-dialog-title">
      <DialogTitle id="rule-dialog-title">{rule ? 'Edytuj regułę' : 'Nowa reguła godzinowa'}</DialogTitle>
      <DialogContent dividers>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="Nazwa (np. Noc)" value={name} onChange={(e) => setName(e.target.value)} fullWidth size="small" />

          <Box>
            <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.75 }}>
              Dni tygodnia
            </Typography>
            <ToggleButtonGroup
              fullWidth
              size="small"
              value={days}
              onChange={(_, v: number[]) => setDays(v)}
              aria-label="Dni tygodnia"
              sx={{ '& .Mui-selected': { fontWeight: 700 } }}
            >
              {DAY_LABELS.map((label, i) => (
                <ToggleButton key={label} value={i} aria-label={label}>
                  {label}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            {days.length === 0 && (
              <Typography variant="caption" color="error">
                Wybierz przynajmniej jeden dzień.
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <TextField
              label="Od"
              type="time"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              size="small"
              fullWidth
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              label="Do"
              type="time"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              size="small"
              fullWidth
              slotProps={{ inputLabel: { shrink: true } }}
              helperText={to < from ? 'Reguła trwa do następnego dnia.' : undefined}
            />
          </Box>

          <Divider />
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Co ma się zmienić w tym czasie?
          </Typography>
          {!hasOverride && (
            <Typography variant="caption" color="text.secondary">
              Włącz przynajmniej jedną zmianę.
            </Typography>
          )}

          <Box>
            {switchRow('walking', 'Tempo pieszo', 'walking' in o)}
            <Collapse in={'walking' in o} unmountOnExit>
              {o.walking && <WalkingSection value={o.walking} onChange={(walking) => setO({ ...o, walking })} />}
            </Collapse>
          </Box>
          <Box>
            {switchRow('cycling', 'Rower', 'cycling' in o)}
            <Collapse in={'cycling' in o} unmountOnExit>
              {o.cycling && <CyclingSection value={o.cycling} onChange={(cycling) => setO({ ...o, cycling })} />}
            </Collapse>
          </Box>
          <Box>
            {switchRow('wheelchair', 'Wózek i dostępność', 'wheelchair' in o)}
            <Collapse in={'wheelchair' in o} unmountOnExit>
              {o.wheelchair && <WheelchairSection value={o.wheelchair} onChange={(wheelchair) => setO({ ...o, wheelchair })} />}
            </Collapse>
          </Box>
          <Box>
            {switchRow('excludedModes', 'Środki transportu', 'excludedModes' in o)}
            <Collapse in={'excludedModes' in o} unmountOnExit>
              {o.excludedModes && (
                <TransportModesSection value={o.excludedModes} onChange={(excludedModes) => setO({ ...o, excludedModes })} />
              )}
            </Collapse>
          </Box>
          <Box>
            {switchRow('maxTransfers', 'Maksymalna liczba przesiadek', hasMaxTransfers)}
            <Collapse in={hasMaxTransfers} unmountOnExit>
              <Box sx={{ pt: 0.5 }}>
                <TransferChips value={o.maxTransfers ?? null} onChange={(maxTransfers) => setO({ ...o, maxTransfers })} />
              </Box>
            </Collapse>
          </Box>
          <Box>
            {switchRow('excluded', 'Wykluczone okolice', 'excluded' in o)}
            <Collapse in={'excluded' in o} unmountOnExit>
              <Box sx={{ pt: 0.5 }}>
                {o.excluded && <AreaPicker value={o.excluded} onChange={(excluded) => setO({ ...o, excluded })} />}
              </Box>
            </Collapse>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 1.5 }}>
        <Button color="inherit" onClick={onClose}>
          Anuluj
        </Button>
        <Button variant="contained" disabled={!valid} onClick={save}>
          Zapisz
        </Button>
      </DialogActions>
    </Dialog>
  );
}
