import { useState, type ReactNode } from 'react';
import { Accordion, AccordionDetails, AccordionSummary, Box, Button, Chip, Drawer, FormControlLabel, Switch, Typography } from '@mui/material';
import ExpandMore from '@mui/icons-material/ExpandMore';
import PreferenceFields, { TransferChips } from './preferences/PreferenceFields';
import AreaPicker from './preferences/AreaPicker';
import {
  BIKE_LEVELS,
  DEFAULT_FILTERS,
  diffOverrides,
  FILTER_MODES,
  modeName,
  SORT_LABELS,
  WALK_LEVELS,
  WHEELCHAIR_LABEL,
  type FilterMode,
  type Preferences,
  type SortKey,
  type TripFilters,
  type WheelchairType,
} from '../preferences/model';
import { RADIUS } from '../layout';

const WALK_LIMITS: (number | null)[] = [null, 5, 10, 15, 20];

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box sx={{ mb: 2.5 }} role="group" aria-label={title}>
      <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.75 }}>
        {title}
      </Typography>
      {children}
    </Box>
  );
}

function ChoiceChip({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) {
  return (
    <Chip
      label={label}
      clickable
      color={selected ? 'primary' : 'default'}
      variant={selected ? 'filled' : 'outlined'}
      aria-pressed={selected}
      onClick={onClick}
    />
  );
}

const Row = ({ children }: { children: ReactNode }) => (
  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>{children}</Box>
);

interface Props {
  open: boolean;
  onClose: () => void;
  filters: TripFilters;
  onChange: (f: TripFilters) => void;
  /** Preferences valid now (before this trip's overrides). */
  effective: Preferences;
  /** Preferences with this trip's overrides applied. */
  trip: Preferences;
  resultCount: number;
}

/** Filters and sorting of the found routes, for this search only. */
export default function FilterSheet({ open, onClose, filters, onChange, effective, trip, resultCount }: Props) {
  const [advanced, setAdvanced] = useState(false);

  const setTrip = (next: Preferences) => onChange({ ...filters, overrides: diffOverrides(effective, next) });
  // The chips start from the preference ("Środki transportu") and override it for this search only.
  const preferred = FILTER_MODES.filter((m) => !trip.excludedModes.includes(m));
  const selectedModes = filters.modes ?? preferred;
  const toggleMode = (m: FilterMode) => {
    const next = FILTER_MODES.filter((x) => (x === m ? !selectedModes.includes(x) : selectedModes.includes(x)));
    onChange({ ...filters, modes: next.length === preferred.length && next.every((x) => preferred.includes(x)) ? null : next });
  };

  return (
    <Drawer
      anchor="bottom"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { borderTopLeftRadius: RADIUS.sheet, borderTopRightRadius: RADIUS.sheet, maxHeight: '90vh' }, 'aria-label': 'Filtry tras' }}
    >
      <Box sx={{ overflowY: 'auto', px: 2.5, pt: 1.25, pb: 1 }}>
        <Box sx={{ maxWidth: 640, mx: 'auto' }}>
          <Box sx={{ display: 'grid', placeItems: 'center', pb: 1.5 }}>
            <Box sx={{ width: 36, height: 4, borderRadius: RADIUS.pill, bgcolor: 'text.disabled', opacity: 0.5 }} />
          </Box>
          <Typography variant="h6" component="h2" sx={{ fontWeight: 700, mb: 0.25 }}>
            Filtry
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Działają tylko dla tego wyszukiwania. Domyślnie trasy są dopasowane do Twoich preferencji.
          </Typography>

          <Group title="Sortowanie">
            <Row>
              {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                <ChoiceChip key={k} label={SORT_LABELS[k]} selected={filters.sort === k} onClick={() => onChange({ ...filters, sort: k })} />
              ))}
            </Row>
          </Group>

          <Group title="Maksymalna liczba przesiadek">
            <TransferChips
              value={trip.priorities.maxTransfers}
              onChange={(maxTransfers) => setTrip({ ...trip, priorities: { ...trip.priorities, maxTransfers } })}
            />
          </Group>

          <Group title="Środki transportu">
            <Row>
              {FILTER_MODES.map((m) => (
                <ChoiceChip key={m} label={modeName(m)} selected={selectedModes.includes(m)} onClick={() => toggleMode(m)} />
              ))}
            </Row>
          </Group>

          <Group title="Maksymalny czas pieszo">
            <Row>
              {WALK_LIMITS.map((n) => (
                <ChoiceChip
                  key={String(n)}
                  label={n === null ? 'Bez limitu' : `${n} min`}
                  selected={filters.maxWalkMin === n}
                  onClick={() => onChange({ ...filters, maxWalkMin: n })}
                />
              ))}
            </Row>
          </Group>

          <Group title="Dostępność">
            <FormControlLabel
              control={
                <Switch
                  checked={trip.wheelchair.stepFree}
                  onChange={(e) => setTrip({ ...trip, wheelchair: { ...trip.wheelchair, stepFree: e.target.checked } })}
                />
              }
              label="Tylko trasy bez schodów"
            />
          </Group>

          <Group title="Tempo na tę jazdę">
            <Typography variant="caption" color="text.secondary">
              Pieszo
            </Typography>
            <Row>
              {WALK_LEVELS.map((l) => (
                <ChoiceChip
                  key={l.id}
                  label={l.label}
                  selected={trip.walking.customKmh === null && trip.walking.level === l.id}
                  onClick={() => setTrip({ ...trip, walking: { ...trip.walking, level: l.id, customKmh: null, autoSpeed: false } })}
                />
              ))}
            </Row>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Rower
            </Typography>
            <Row>
              <ChoiceChip
                label="Bez roweru"
                selected={!trip.cycling.enabled}
                onClick={() => setTrip({ ...trip, cycling: { ...trip.cycling, enabled: false } })}
              />
              {BIKE_LEVELS.map((l) => (
                <ChoiceChip
                  key={l.id}
                  label={l.label}
                  selected={trip.cycling.enabled && trip.cycling.customKmh === null && trip.cycling.level === l.id}
                  onClick={() => setTrip({ ...trip, cycling: { ...trip.cycling, enabled: true, level: l.id, customKmh: null, autoSpeed: false } })}
                />
              ))}
            </Row>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Wózek
            </Typography>
            <Row>
              {(Object.keys(WHEELCHAIR_LABEL) as WheelchairType[]).map((t) => (
                <ChoiceChip
                  key={t}
                  label={WHEELCHAIR_LABEL[t]}
                  selected={trip.wheelchair.type === t}
                  onClick={() => setTrip({ ...trip, wheelchair: { ...trip.wheelchair, type: t } })}
                />
              ))}
            </Row>
          </Group>

          <Group title="Wykluczone okolice na tę jazdę">
            <AreaPicker
              value={trip.priorities.excluded}
              onChange={(excluded) => setTrip({ ...trip, priorities: { ...trip.priorities, excluded } })}
            />
          </Group>

          <Accordion
            disableGutters
            elevation={0}
            expanded={advanced}
            onChange={(_, v) => setAdvanced(v)}
            sx={{ '&:before': { display: 'none' }, bgcolor: 'transparent', mb: 1 }}
          >
            <AccordionSummary expandIcon={<ExpandMore />} sx={{ px: 0 }}>
              <Typography sx={{ fontWeight: 700 }}>Zaawansowane: wszystkie preferencje na tę jazdę</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 0 }}>
              <PreferenceFields value={trip} onChange={setTrip} />
            </AccordionDetails>
          </Accordion>
        </Box>
      </Box>

      <Box sx={{ px: 2.5, py: 1.5, display: 'flex', gap: 1.5, borderTop: 1, borderColor: 'divider', pb: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
        <Button color="inherit" onClick={() => onChange(DEFAULT_FILTERS)} sx={{ flexShrink: 0, whiteSpace: "nowrap" }}>
          Wyczyść filtry
        </Button>
        <Button variant="contained" fullWidth onClick={onClose}>
          Pokaż trasy ({resultCount})
        </Button>
      </Box>
    </Drawer>
  );
}
