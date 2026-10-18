import { Fragment } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import ChevronRight from '@mui/icons-material/ChevronRight';
import { MODE_META, modeColor } from '../modes';
import type { LegDelay, RouteLeg } from '../types';
import { legDelayKind, legDelayLabel } from '../api/routeDelays';
import { RADIUS } from '../layout';

/** Chain of icons showing the stages of a journey: walk > bike > metro ...
 * `delays` (aligned with `legs`) adds the live delay of a bus / tram ride, e.g. "504 · 12′ · +3 min". */
export default function LegChain({ legs, delays }: { legs: RouteLeg[]; delays?: (LegDelay | undefined)[] }) {
  const theme = useTheme();
  const palette = theme.palette.mode;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}>
      {legs.map((leg, i) => {
        const Icon = MODE_META[leg.mode].icon;
        const color = modeColor(leg.mode, palette);
        const delay = delays?.[i];
        const kind = delay ? legDelayKind(delay) : null;
        return (
          <Fragment key={`${i}-${leg.mode}`}>
            {i > 0 && <ChevronRight sx={{ fontSize: 16, color: 'text.disabled' }} />}
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.5,
                pl: 0.5,
                pr: 1,
                py: 0.25,
                borderRadius: RADIUS.pill,
                bgcolor: `${color}22`,
                color,
              }}
            >
              <Icon sx={{ fontSize: 18 }} />
              <Typography variant="caption" sx={{ fontWeight: 700, lineHeight: 1, color: 'text.primary' }}>
                {leg.line ? `${leg.line} · ` : ''}
                {leg.durationMin}′
              </Typography>
              {delay && (
                <Typography
                  variant="caption"
                  title={delay.sameTrip ? 'Opóźnienie na żywo' : 'Prognoza: pojazd kończy jeszcze poprzedni kurs'}
                  sx={{
                    fontWeight: 700,
                    lineHeight: 1,
                    color: kind === 'late' ? 'error.main' : kind === 'early' ? 'success.main' : 'text.secondary',
                  }}
                >
                  · {legDelayLabel(delay)}
                </Typography>
              )}
            </Box>
          </Fragment>
        );
      })}
    </Box>
  );
}
