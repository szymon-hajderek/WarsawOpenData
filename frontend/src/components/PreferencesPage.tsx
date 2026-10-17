import { useState } from 'react';
import { alpha, Box, Button, Chip, IconButton, Typography } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Delete from '@mui/icons-material/Delete';
import Edit from '@mui/icons-material/Edit';
import Schedule from '@mui/icons-material/Schedule';
import RestartAlt from '@mui/icons-material/RestartAlt';
import PreferenceFields, { Section } from './preferences/PreferenceFields';
import RuleDialog from './preferences/RuleDialog';
import { usePreferences } from '../preferences/PreferencesProvider';
import { DEFAULT_PREFERENCES, describeRule, type PreferenceOverrides, type TimeRule } from '../preferences/model';
import { BOTTOM_NAV_HEIGHT } from '../layout';

const OVERRIDE_LABELS: Record<keyof PreferenceOverrides, string> = {
  walking: 'Pieszo',
  cycling: 'Rower',
  wheelchair: 'Wózek',
  maxTransfers: 'Przesiadki',
  excluded: 'Okolice',
};

/** Preferences tab: how the user moves, priorities and time rules. */
export default function PreferencesPage() {
  const { base, rules, activeRule, setBase, setRules, reset } = usePreferences();
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
            sx={(t) => ({ mb: 2, p: 1.5, borderRadius: 3, bgcolor: alpha(t.palette.secondary.main, 0.14), display: 'flex', gap: 1, alignItems: 'center' })}
          >
            <Schedule color="secondary" />
            <Typography variant="body2">
              Teraz działa reguła <b>{activeRule.name}</b> ({describeRule(activeRule)}).
            </Typography>
          </Box>
        )}

        <PreferenceFields value={base} onChange={setBase} />

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
                    borderRadius: 3,
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
