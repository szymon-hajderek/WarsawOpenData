import { alpha, Badge, Box, Button, Chip, CircularProgress, Typography } from '@mui/material';
import Tune from '@mui/icons-material/Tune';
import Schedule from '@mui/icons-material/Schedule';
import LocalFireDepartment from '@mui/icons-material/LocalFireDepartment';
import Sheet from './Sheet';
import LegChain from './LegChain';
import { formatCost, formatDuration, stopsLabel, transfersLabel } from '../utils/format';
import type { FilterChip, TimeRule } from '../preferences/model';
import type { RouteOption } from '../types';
import { RADIUS } from '../layout';

interface Props {
  /** Routes after filtering and sorting. */
  options: RouteOption[];
  /** How many routes were found before filtering. */
  foundCount: number;
  loading: boolean;
  selectedId: string | null;
  /** Short summary of the preferences the routes follow. */
  summary: string[];
  /** Time rule active right now, if any. */
  activeRule: TimeRule | null;
  /** Chips of the filters that differ from the defaults. */
  chips: FilterChip[];
  onSelect: (id: string) => void;
  onOpenFilters: () => void;
  onClearChip: (id: FilterChip['id']) => void;
  onClearAll: () => void;
  onConfirm: () => void;
}

/** List of connections - "Choose your route" - with the preference summary and filters. */
export default function RouteOptionsSheet({
  options,
  foundCount,
  loading,
  selectedId,
  summary,
  activeRule,
  chips,
  onSelect,
  onOpenFilters,
  onClearChip,
  onClearAll,
  onConfirm,
}: Props) {
  const noScrollbar = { scrollbarWidth: 'none', '&::-webkit-scrollbar': { display: 'none' } } as const;

  return (
    <Sheet maxHeight={{ xs: '54vh', sm: 'calc(100vh - 200px)' }}>
      <Box sx={{ px: 2.5, pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, flex: 1 }}>
            Wybierz trasę
          </Typography>
          <Badge badgeContent={chips.length} color="primary" overlap="rectangular">
            <Button variant="outlined" size="small" startIcon={<Tune />} onClick={onOpenFilters} sx={{ py: 0.75 }}>
              Filtry
            </Button>
          </Badge>
        </Box>

        <Box sx={{ display: 'flex', gap: 1, mt: 1, overflowX: 'auto', alignItems: 'center', ...noScrollbar }}>
          {activeRule && (
            <Chip
              icon={<Schedule />}
              label={`Reguła: ${activeRule.name}`}
              size="small"
              color="secondary"
              sx={{ flexShrink: 0 }}
            />
          )}
          {chips.map((c) => (
            <Chip
              key={c.id}
              label={c.label}
              size="small"
              color="primary"
              onDelete={() => onClearChip(c.id)}
              sx={{ flexShrink: 0 }}
            />
          ))}
        </Box>
        <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block', mt: 0.75 }} title={summary.join(' · ')}>
          Dla Ciebie: {summary.join(' · ')}
        </Typography>
      </Box>

      <Box sx={{ flex: 1, overflowY: 'auto', px: 1.5, minHeight: 120 }}>
        {loading && (
          <Box sx={{ display: 'grid', placeItems: 'center', py: 5 }}>
            <CircularProgress size={32} />
          </Box>
        )}
        {!loading && options.length === 0 && (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              {foundCount > 0 ? 'Żadna trasa nie spełnia wybranych filtrów.' : 'Nie znaleziono połączeń.'}
            </Typography>
            {foundCount > 0 && (
              <Button onClick={onClearAll} sx={{ mt: 1 }}>
                Wyczyść filtry
              </Button>
            )}
          </Box>
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
                  borderRadius: RADIUS.tile,
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
                    {o.waypoints && o.waypoints.length > 2 && ` · ${stopsLabel(o.waypoints.length - 2)}`}
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
