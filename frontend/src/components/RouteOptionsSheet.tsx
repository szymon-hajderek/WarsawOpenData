import { alpha, Box, Button, Chip, CircularProgress, Typography } from '@mui/material';
import Accessible from '@mui/icons-material/Accessible';
import DirectionsWalk from '@mui/icons-material/DirectionsWalk';
import Elderly from '@mui/icons-material/Elderly';
import LocalFireDepartment from '@mui/icons-material/LocalFireDepartment';
import Sheet from './Sheet';
import LegChain from './LegChain';
import { formatCost, formatDuration, transfersLabel } from '../utils/format';
import type { Profile, RouteOption } from '../types';

const PROFILES: { id: Profile; label: string; hint: string; icon: JSX.Element }[] = [
  { id: 'standard', label: 'Standard', hint: 'Standardowe tempo marszu i jazdy', icon: <DirectionsWalk /> },
  { id: 'slow', label: 'Wolniej', hint: 'Spokojniejsze tempo marszu i jazdy', icon: <Elderly /> },
  { id: 'accessible', label: 'Wózek', hint: 'Wózek / dostępność: trasy bez roweru, wolniejszy marsz', icon: <Accessible /> },
];

interface Props {
  options: RouteOption[];
  loading: boolean;
  selectedId: string | null;
  profile: Profile;
  onSelect: (id: string) => void;
  onProfileChange: (p: Profile) => void;
  onConfirm: () => void;
}

/** List of connections - "Choose your route". */
export default function RouteOptionsSheet({
  options,
  loading,
  selectedId,
  profile,
  onSelect,
  onProfileChange,
  onConfirm,
}: Props) {
  return (
    <Sheet>
      <Box sx={{ px: 2.5, pb: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          Wybierz trasę
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, mt: 1, overflowX: 'auto', scrollbarWidth: 'none', '&::-webkit-scrollbar': { display: 'none' } }}>
          {PROFILES.map((p) => (
            <Chip
              key={p.id}
              icon={p.icon}
              label={p.label}
              title={p.hint}
              clickable
              color={profile === p.id ? 'primary' : 'default'}
              variant={profile === p.id ? 'filled' : 'outlined'}
              onClick={() => onProfileChange(p.id)}
              sx={{ flexShrink: 0 }}
            />
          ))}
        </Box>
      </Box>

      <Box sx={{ flex: 1, overflowY: 'auto', px: 1.5, minHeight: 120 }}>
        {loading && (
          <Box sx={{ display: 'grid', placeItems: 'center', py: 5 }}>
            <CircularProgress size={32} />
          </Box>
        )}
        {!loading && options.length === 0 && (
          <Typography color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
            Nie znaleziono połączeń dla tego profilu.
          </Typography>
        )}
        {!loading &&
          options.map((o) => {
            const selected = o.id === selectedId;
            return (
              <Box
                key={o.id}
                role="button"
                tabIndex={0}
                aria-pressed={selected}
                onClick={() => onSelect(o.id)}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(o.id)}
                sx={(t) => ({
                  display: 'flex',
                  gap: 1.5,
                  p: 1.5,
                  my: 0.75,
                  borderRadius: 4,
                  cursor: 'pointer',
                  border: 2,
                  borderColor: selected ? 'primary.main' : 'transparent',
                  bgcolor: selected ? alpha(t.palette.primary.main, 0.1) : 'transparent',
                  transition: 'background-color .15s, border-color .15s',
                  '&:hover': { bgcolor: alpha(t.palette.primary.main, selected ? 0.12 : 0.06) },
                  '&:focus-visible': { outline: `2px solid ${t.palette.primary.main}`, outlineOffset: 2 },
                })}
              >
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Typography sx={{ fontWeight: 700 }}>{o.title}</Typography>
                    {o.tags.map((tag) => (
                      <Chip key={tag} label={tag} size="small" color="secondary" variant="outlined" />
                    ))}
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 0.75 }}>
                    {o.departure} – {o.arrival} · {transfersLabel(o.transfers)}
                  </Typography>
                  <LegChain legs={o.legs} />
                </Box>

                <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                    {formatDuration(o.durationMin)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {o.costPln > 0 ? '~' : ''}
                    {formatCost(o.costPln)}
                  </Typography>
                  {o.calories > 0 && (
                    <Typography
                      variant="caption"
                      color="secondary"
                      sx={{ display: 'inline-flex', alignItems: 'center', fontWeight: 600 }}
                    >
                      <LocalFireDepartment sx={{ fontSize: 14 }} />
                      {o.calories} kcal
                    </Typography>
                  )}
                </Box>
              </Box>
            );
          })}
      </Box>

      <Box sx={{ p: 2 }}>
        <Button fullWidth variant="contained" size="large" disabled={!selectedId || loading} onClick={onConfirm}>
          Wybierz tę trasę
        </Button>
      </Box>
    </Sheet>
  );
}
