import { useEffect, useRef } from 'react';
import { alpha, Badge, Box, Button, Chip, CircularProgress, Typography } from '@mui/material';
import Tune from '@mui/icons-material/Tune';
import Schedule from '@mui/icons-material/Schedule';
import LocalFireDepartment from '@mui/icons-material/LocalFireDepartment';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import SnapSheet, { type SheetSnap } from './SnapSheet';
import LegChain from './LegChain';
import { pressableProps } from './pressable';
import { formatDuration, stopsLabel, transfersLabel } from '../utils/format';
import { routeKcal, type FilterChip, type TimeRule } from '../preferences/model';
import { usePreferences } from '../preferences/PreferencesProvider';
import type { RouteOption } from '../types';
import { RADIUS } from '../layout';

interface Props {
  /** Routes after filtering and sorting. */
  options: RouteOption[];
  /** How many routes were found before filtering. */
  foundCount: number;
  loading: boolean;
  /** The search failed (no routes, not even example ones). */
  error: boolean;
  /** The routes are made-up example data. */
  mock: boolean;
  selectedId: string | null;
  /** Short summary of the preferences the routes follow. */
  summary: string[];
  /** Time rule active right now, if any. */
  activeRule: TimeRule | null;
  /** Chips of the filters that differ from the defaults. */
  chips: FilterChip[];
  snap: SheetSnap;
  onSnapChange: (snap: SheetSnap) => void;
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
  error,
  mock,
  selectedId,
  summary,
  activeRule,
  chips,
  snap,
  onSnapChange,
  onSelect,
  onOpenFilters,
  onClearChip,
  onClearAll,
  onConfirm,
}: Props) {
  const noScrollbar = { scrollbarWidth: 'none', '&::-webkit-scrollbar': { display: 'none' } } as const;
  const { effective } = usePreferences();
  const content = useRef<HTMLDivElement>(null);
  const fastest = options.length ? Math.min(...options.map((o) => o.durationMin)) : null;

  // Below the full height only a part of the list is visible: bring the selected route into view
  // (the filters row stays visible when the selected route is already on screen).
  useEffect(() => {
    if (snap === 'full') return;
    const box = content.current;
    const row = box?.querySelector<HTMLElement>(`[data-route-id="${selectedId}"]`);
    if (!box || !row) return;
    const b = box.getBoundingClientRect();
    const r = row.getBoundingClientRect();
    if (r.top >= b.top && r.bottom <= b.bottom) return;
    box.scrollTo({ top: Math.max(0, r.top - b.top + box.scrollTop - 8), behavior: 'smooth' });
  }, [snap, selectedId, options]);

  return (
    <SnapSheet
      snap={snap}
      onSnapChange={onSnapChange}
      middleHeight={352}
      ariaLabel="Lista tras"
      contentRef={content}
      header={({ barLike, full }) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.25 }}>
              Wybierz trasę
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {loading
                ? 'Szukam połączeń…'
                : options.length === 0
                  ? 'Brak tras'
                  : `${options.length} ${options.length === 1 ? 'trasa' : 'tras'}${fastest !== null ? ` · najszybsza ${formatDuration(fastest)}` : ''}`}
            </Typography>
          </Box>
          {barLike || !full ? <ExpandLess color="action" /> : <ExpandMore color="action" />}
        </Box>
      )}
      toolbar={
        <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Badge badgeContent={chips.length} color="primary" overlap="rectangular" sx={{ flexShrink: 0 }}>
          <Button variant="outlined" size="small" startIcon={<Tune />} onClick={onOpenFilters} sx={{ py: 0.75 }}>
            Filtry
          </Button>
        </Badge>
        <Box sx={{ display: 'flex', gap: 1, overflowX: 'auto', alignItems: 'center', minWidth: 0, ...noScrollbar }}>
          {activeRule && (
            <Chip
              icon={<Schedule />}
              label={`Reguła: ${activeRule.name}`}
              size="small"
              color="secondary"
              sx={{ flexShrink: 0 }}
            />
          )}
          {mock && <Chip label="Dane przykładowe" size="small" color="warning" sx={{ flexShrink: 0 }} />}
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
      </Box>
      <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block', mt: 0.75 }} title={summary.join(' · ')}>
        Dla Ciebie: {summary.join(' · ')}
      </Typography>
        </>
      }
      footer={
        <Button fullWidth variant="contained" size="large" disabled={!selectedId || loading} onClick={onConfirm}>
          Wybierz tę trasę
        </Button>
      }
    >
      <Box sx={{ mt: 0.5 }}>
        {loading && (
          <Box sx={{ display: 'grid', placeItems: 'center', py: 5 }}>
            <CircularProgress size={32} />
          </Box>
        )}
        {!loading && options.length === 0 && (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              {error
                ? 'Nie udało się pobrać tras. Spróbuj zmienić punkty.'
                : foundCount > 0
                  ? 'Żadna trasa nie spełnia wybranych filtrów.'
                  : 'Nie znaleziono połączeń.'}
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
                data-route-id={o.id}
                {...pressableProps(selected, () => onSelect(o.id))}
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
                  {routeKcal(o, effective) > 0 && (
                    <Typography
                      variant="caption"
                      color="secondary"
                      sx={{ display: 'inline-flex', alignItems: 'center', fontWeight: 600 }}
                    >
                      <LocalFireDepartment sx={{ fontSize: 14 }} />
                      {routeKcal(o, effective)} kcal
                    </Typography>
                  )}
                </Box>
              </Box>
            );
          })}
      </Box>
    </SnapSheet>
  );
}
