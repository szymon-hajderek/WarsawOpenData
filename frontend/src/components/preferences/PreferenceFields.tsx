import type { ReactNode } from 'react';
import { alpha, Box, Chip, FormControlLabel, Switch, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import DirectionsWalk from '@mui/icons-material/DirectionsWalk';
import DirectionsBike from '@mui/icons-material/DirectionsBike';
import Accessible from '@mui/icons-material/Accessible';
import SwapHoriz from '@mui/icons-material/SwapHoriz';
import LevelSelector from './LevelSelector';
import HistoryHint, { type HistoryInfo } from './HistoryHint';
import AreaPicker from './AreaPicker';
import type { SpeedSummary } from '../../history/types';
import {
  BIKE_LEVELS,
  cyclingKmh,
  SPEED_RANGE,
  walkingKmh,
  wheelchairKmh,
  type AutoSpeeds,
  WALK_LEVELS,
  WHEELCHAIR_LABEL,
  WHEELCHAIR_LEVELS,
  type CyclingSetting,
  type Preferences,
  type WalkingSetting,
  type WheelchairSetting,
  type WheelchairType,
} from '../../preferences/model';
import { RADIUS } from '../../layout';

/** Tonal card for one group of settings. */
export function Section({ icon, title, hint, children }: { icon: ReactNode; title: string; hint?: string; children: ReactNode }) {
  return (
    <Box
      component="section"
      aria-label={title}
      sx={(t) => ({ p: 2, borderRadius: RADIUS.card, bgcolor: alpha(t.palette.primary.main, 0.05) })}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: hint ? 0.25 : 1.5, color: 'primary.main' }}>
        {icon}
        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'text.primary' }}>
          {title}
        </Typography>
      </Box>
      {hint && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {hint}
        </Typography>
      )}
      {children}
    </Box>
  );
}

export function WalkingSection({
  value,
  onChange,
  history,
}: {
  value: WalkingSetting;
  onChange: (v: WalkingSetting) => void;
  /** The trip history of this mode; shown on the Preferences page only. */
  history?: HistoryInfo;
}) {
  const locked = history?.used != null;
  return (
    <Section icon={<DirectionsWalk />} title="Pieszo" hint="Twoje tempo marszu.">
      <LevelSelector
        ariaLabel="Tempo pieszo"
        levels={WALK_LEVELS}
        level={value.level}
        customKmh={value.customKmh}
        range={SPEED_RANGE.walking}
        disabled={locked}
        onChange={(level, customKmh) => onChange({ ...value, level, customKmh })}
      />
      {history && (
        <HistoryHint
          {...history}
          currentKmh={walkingKmh(value)}
          range={SPEED_RANGE.walking}
          autoSpeed={value.autoSpeed}
          onAutoChange={(autoSpeed) => onChange({ ...value, autoSpeed })}
          onUse={(kmh) => onChange({ ...value, customKmh: kmh })}
        />
      )}
    </Section>
  );
}

export function CyclingSection({
  value,
  onChange,
  history,
}: {
  value: CyclingSetting;
  onChange: (v: CyclingSetting) => void;
  history?: HistoryInfo;
}) {
  const locked = history?.used != null;
  return (
    <Section icon={<DirectionsBike />} title="Rower Veturilo" hint="Poziom jazdy na rowerze.">
      <FormControlLabel
        control={<Switch checked={value.enabled} onChange={(e) => onChange({ ...value, enabled: e.target.checked })} />}
        label="Korzystam z roweru"
        sx={{ mb: 1 }}
      />
      {value.enabled && (
        <>
          <LevelSelector
            ariaLabel="Poziom jazdy na rowerze"
            levels={BIKE_LEVELS}
            level={value.level}
            customKmh={value.customKmh}
            range={SPEED_RANGE.cycling}
            disabled={locked}
            onChange={(level, customKmh) => onChange({ ...value, level, customKmh })}
          />
          {history && (
            <HistoryHint
              {...history}
              currentKmh={cyclingKmh(value)}
              range={SPEED_RANGE.cycling}
              autoSpeed={value.autoSpeed}
              onAutoChange={(autoSpeed) => onChange({ ...value, autoSpeed })}
              onUse={(kmh) => onChange({ ...value, customKmh: kmh })}
            />
          )}
        </>
      )}
    </Section>
  );
}

export function WheelchairSection({
  value,
  onChange,
  history,
}: {
  value: WheelchairSetting;
  onChange: (v: WheelchairSetting) => void;
  history?: HistoryInfo;
}) {
  const locked = history?.used != null;
  return (
    <Section icon={<Accessible />} title="Wózek i dostępność" hint="Aplikacja ma działać dla każdego.">
      <ToggleButtonGroup
        exclusive
        fullWidth
        size="small"
        aria-label="Rodzaj wózka"
        value={value.type}
        onChange={(_, v: WheelchairType | null) => v && onChange({ ...value, type: v })}
        sx={{ mb: 1.5, '& .MuiToggleButton-root': { textTransform: 'none' }, '& .Mui-selected': { fontWeight: 700 } }}
      >
        {(Object.keys(WHEELCHAIR_LABEL) as WheelchairType[]).map((t) => (
          <ToggleButton key={t} value={t}>
            {WHEELCHAIR_LABEL[t]}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      {value.type !== 'none' && (
        <Box sx={{ mb: 1.5 }}>
          <LevelSelector
            ariaLabel="Tempo na wózku"
            levels={WHEELCHAIR_LEVELS[value.type]}
            level={value.level}
            customKmh={value.customKmh}
            range={SPEED_RANGE.wheelchair}
            disabled={locked}
            onChange={(level, customKmh) => onChange({ ...value, level, customKmh })}
          />
          {history && (
            <HistoryHint
              {...history}
              currentKmh={wheelchairKmh(value) ?? 3.6}
              range={SPEED_RANGE.wheelchair}
              autoSpeed={value.autoSpeed}
              onAutoChange={(autoSpeed) => onChange({ ...value, autoSpeed })}
              onUse={(kmh) => onChange({ ...value, customKmh: kmh })}
            />
          )}
        </Box>
      )}

      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        <FormControlLabel
          control={<Switch checked={value.stepFree} onChange={(e) => onChange({ ...value, stepFree: e.target.checked })} />}
          label="Tylko trasy bez schodów"
        />
        <FormControlLabel
          control={<Switch checked={value.lowFloorOnly} onChange={(e) => onChange({ ...value, lowFloorOnly: e.target.checked })} />}
          label="Tylko pojazdy niskopodłogowe"
        />
        <FormControlLabel
          control={<Switch checked={value.preferLifts} onChange={(e) => onChange({ ...value, preferLifts: e.target.checked })} />}
          label="Preferuj windy zamiast schodów"
        />
      </Box>
    </Section>
  );
}

const TRANSFER_CHOICES: { value: number | null; label: string }[] = [
  { value: null, label: 'Dowolnie' },
  { value: 0, label: 'Bez przesiadek' },
  { value: 1, label: '1' },
  { value: 2, label: '2' },
  { value: 3, label: '3' },
];

/** Choice of the maximum number of transfers (null = any). */
export function TransferChips({ value, onChange }: { value: number | null; onChange: (v: number | null) => void }) {
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }} role="group" aria-label="Maksymalna liczba przesiadek">
      {TRANSFER_CHOICES.map((c) => {
        const selected = value === c.value;
        return (
          <Chip
            key={String(c.value)}
            label={c.label}
            clickable
            color={selected ? 'primary' : 'default'}
            variant={selected ? 'filled' : 'outlined'}
            aria-pressed={selected}
            onClick={() => onChange(c.value)}
          />
        );
      })}
    </Box>
  );
}

export function PrioritiesSection({
  value,
  onChange,
}: {
  value: Preferences['priorities'];
  onChange: (v: Preferences['priorities']) => void;
}) {
  return (
    <Section icon={<SwapHoriz />} title="Priorytety" hint="Ile przesiadek akceptujesz i których okolic unikasz.">
      <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.75 }}>
        Maksymalna liczba przesiadek
      </Typography>
      <Box sx={{ mb: 2 }}>
        <TransferChips value={value.maxTransfers} onChange={(maxTransfers) => onChange({ ...value, maxTransfers })} />
      </Box>
      <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.75 }}>
        Wykluczone okolice
      </Typography>
      <AreaPicker value={value.excluded} onChange={(excluded) => onChange({ ...value, excluded })} />
    </Section>
  );
}

/** All preference sections. Used on the Preferences page and (as overrides) in the trip filters. */
export default function PreferenceFields({
  value,
  onChange,
  history,
}: {
  value: Preferences;
  onChange: (next: Preferences) => void;
  /** Trip history of each mode; only the Preferences page passes it. */
  history?: { summary: SpeedSummary; used: AutoSpeeds };
}) {
  const info = (mode: 'walking' | 'cycling' | 'wheelchair'): HistoryInfo | undefined =>
    history && { summary: history.summary[mode], used: history.used[mode]?.kmh ?? null };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <WalkingSection value={value.walking} onChange={(walking) => onChange({ ...value, walking })} history={info('walking')} />
      <CyclingSection value={value.cycling} onChange={(cycling) => onChange({ ...value, cycling })} history={info('cycling')} />
      <WheelchairSection
        value={value.wheelchair}
        onChange={(wheelchair) => onChange({ ...value, wheelchair })}
        history={value.wheelchair.type === 'none' ? undefined : info('wheelchair')}
      />
      <PrioritiesSection value={value.priorities} onChange={(priorities) => onChange({ ...value, priorities })} />
    </Box>
  );
}
