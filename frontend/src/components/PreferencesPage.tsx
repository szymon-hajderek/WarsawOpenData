import { useState } from 'react';
import { alpha, Box, Button, Chip, FormControlLabel, IconButton, Switch, Typography } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Delete from '@mui/icons-material/Delete';
import Edit from '@mui/icons-material/Edit';
import Schedule from '@mui/icons-material/Schedule';
import RestartAlt from '@mui/icons-material/RestartAlt';
import HistoryIcon from '@mui/icons-material/History';
import PreferenceFields, { Section } from './preferences/PreferenceFields';
import BodySection from './preferences/BodySection';
import ViewSection from './preferences/ViewSection';
import RuleDialog from './preferences/RuleDialog';
import { usePreferences } from '../preferences/PreferencesProvider';
import { useHistory } from '../history/HistoryProvider';
import { tripsLabel } from './preferences/HistoryHint';
import { DEFAULT_PREFERENCES, describeRule, type PreferenceOverrides, type TimeRule } from '../preferences/model';
import { BOTTOM_NAV_HEIGHT, RADIUS } from '../layout';

const OVERRIDE_LABELS: Record<keyof PreferenceOverrides, string> = {
  walking: 'Pieszo',
  cycling: 'Rower',
  wheelchair: 'Wózek',
  maxTransfers: 'Przesiadki',
  excluded: 'Okolice',
  excludedModes: 'Pojazdy',
};

/** Preferences tab: how the user moves, priorities and time rules. */
export default function PreferencesPage() {
  const { base, rules, activeRule, autoUsed, setBase, setRules, reset } = usePreferences();
  const { summary, records, clear, shareJourneys, setShareJourneys } = useHistory();
  const [editing, setEditing] = useState<TimeRule | 'new' | null>(null);

  const saveRule = (rule: TimeRule) => {
    setRules(rules.some((r) => r.id === rule.id) ? rules.map((r) => (r.id === rule.id ? rule : r)) : [...rules, rule]);
    setEditing(null);
  };

  return (
    <Box
      sx={{
        position: 'absolute',
        inset: 0,
        zIndex: 1100,
        bgcolor: 'background.default',
        overflowY: 'auto',
        pb: `calc(env(safe-area-inset-bottom) + ${BOTTOM_NAV_HEIGHT + 24}px)`,
      }}
    >
      <Box sx={{ maxWidth: 640, mx: 'auto', px: 2, pt: 'calc(env(safe-area-inset-top) + 20px)' }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 700 }}>
          Preferencje
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Powiedz nam, jak się poruszasz. Trasy będą wybierane z myślą o Tobie.
        </Typography>

        {activeRule && (
          <Box
            role="status"
            sx={(t) => ({ mb: 2, p: 1.5, borderRadius: RADIUS.tile, bgcolor: alpha(t.palette.secondary.main, 0.14), display: 'flex', gap: 1, alignItems: 'center' })}
          >
            <Schedule color="secondary" />
            <Typography variant="body2">
              Teraz działa reguła <b>{activeRule.name}</b> ({describeRule(activeRule)}).
            </Typography>
          </Box>
        )}

        <PreferenceFields value={base} onChange={setBase} history={{ summary, used: autoUsed }} />

        <Box sx={{ mt: 1.5 }}>
          <BodySection value={base.body} onChange={(body) => setBase({ ...base, body })} />
        </Box>

        <Box sx={{ mt: 1.5 }}>
          <ViewSection />
        </Box>

        <Box sx={{ mt: 1.5 }}>
          <Section
            icon={<Schedule />}
            title="Reguły godzinowe"
            hint="Zmień wybrane preferencje o danej porze, np. nocą omijaj niebezpieczne dzielnice."
          >
            {rules.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Nie masz jeszcze żadnych reguł.
              </Typography>
            )}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 1.5 }}>
              {rules.map((r) => (
                <Box
                  key={r.id}
                  sx={(t) => ({
                    p: 1.5,
                    borderRadius: RADIUS.tile,
                    bgcolor: t.palette.background.paper,
                    border: 1,
                    borderColor: activeRule?.id === r.id ? 'secondary.main' : 'divider',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                  })}
                >
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                      <Typography sx={{ fontWeight: 700 }}>{r.name}</Typography>
                      {activeRule?.id === r.id && <Chip label="Aktywna teraz" size="small" color="secondary" />}
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                      {describeRule(r)}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
                      {(Object.keys(r.overrides) as (keyof PreferenceOverrides)[]).map((k) => (
                        <Chip key={k} label={OVERRIDE_LABELS[k]} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </Box>
                  <IconButton aria-label={`Edytuj regułę: ${r.name}`} onClick={() => setEditing(r)}>
                    <Edit />
                  </IconButton>
                  <IconButton aria-label={`Usuń regułę: ${r.name}`} onClick={() => setRules(rules.filter((x) => x.id !== r.id))}>
                    <Delete />
                  </IconButton>
                </Box>
              ))}
            </Box>
            <Button variant="outlined" startIcon={<Add />} onClick={() => setEditing('new')}>
              Dodaj regułę
            </Button>
          </Section>
        </Box>

        <Box sx={{ mt: 1.5 }}>
          <Section
            icon={<HistoryIcon />}
            title="Historia przejazdów"
            hint="Z niej liczymy Twoją średnią prędkość. Zostaje tylko na tym urządzeniu."
          >
            {records.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                Nie zapisano jeszcze żadnego przejazdu. W widoku trasy wybierz „Rozpocznij przejazd”.
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 1.5 }}>
                {(['walking', 'cycling', 'wheelchair'] as const)
                  .filter((m) => summary[m].trips > 0)
                  .map((m) => (
                    <Chip
                      key={m}
                      size="small"
                      variant="outlined"
                      label={`${{ walking: 'Pieszo', cycling: 'Rower', wheelchair: 'Wózek' }[m]}: ${tripsLabel(summary[m].trips)}`}
                    />
                  ))}
              </Box>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
              Ślad GPS jest wysyłany do serwera na czas obliczeń i nie jest przechowywany. Historia na tym urządzeniu zawiera wyłącznie dystans, czas ruchu i prędkość, bez współrzędnych.
            </Typography>
            <Button variant="outlined" color="inherit" disabled={records.length === 0} onClick={clear}>
              Wyczyść historię przejazdów
            </Button>
          </Section>
        </Box>

        <Box sx={{ mt: 1.5 }}>
          <Section icon={<HistoryIcon />} title="Statystyki podróży" hint="Pomóż nam lepiej planować transport w Warszawie.">
            <FormControlLabel
              control={<Switch checked={shareJourneys} onChange={(_, enabled) => setShareJourneys(enabled)} />}
              label="Udostępniaj dane podróży do badań miasta"
            />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
              Zapisujemy wyszukiwania, wybrane trasy, rozpoczęcie, zakończenie lub przerwanie nagrywania,
              planowane odcinki, przedział wieku z ustawień kalorii i dostępność związanych stacji Veturilo.
              Miejsca zastępujemy heksagonami, zachowujemy identyfikatory stacji. Bez śladu GPS i stałego
              identyfikatora użytkownika. Dane godzinowe są dostępne tylko dla miasta, do 12 miesięcy.
              Wyłączenie zatrzymuje nowe wysyłki; nie usuwa wcześniej przekazanych danych.
            </Typography>
          </Section>
        </Box>

        <Button
          color="inherit"
          startIcon={<RestartAlt />}
          sx={{ mt: 2, opacity: 0.8 }}
          disabled={JSON.stringify(base) === JSON.stringify(DEFAULT_PREFERENCES) && rules.length === 0}
          onClick={reset}
        >
          Przywróć domyślne
        </Button>
      </Box>

      {editing && (
        <RuleDialog
          rule={editing === 'new' ? null : editing}
          base={base}
          onSave={saveRule}
          onClose={() => setEditing(null)}
        />
      )}
    </Box>
  );
}
