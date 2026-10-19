import { Box, Button, CircularProgress, Paper, Typography } from '@mui/material';
import AddLocationAlt from '@mui/icons-material/AddLocationAlt';
import { useSheetDock } from './SnapSheet';
import { RADIUS } from '../layout';
import type { PickTarget } from './SearchCard';

interface Props {
  target: PickTarget;
  /** The tapped point is being named (nearest stop). */
  busy: boolean;
  onCancel: () => void;
}

const targetName = (t: PickTarget) => (t === 'origin' ? 'start' : t === 'destination' ? 'cel' : `przystanek ${t + 1}`);

/** Shown instead of the search card while a point is picked on the map ("Wybierz na mapie"). */
export default function PickBanner({ target, busy, onCancel }: Props) {
  const docked = useSheetDock();
  return (
    <Paper
      role="status"
      elevation={docked ? 0 : 4}
      variant={docked ? 'outlined' : 'elevation'}
      sx={{
        position: 'absolute',
        zIndex: 1000,
        top: 'calc(env(safe-area-inset-top) + 12px)',
        left: { xs: 12, sm: 16 },
        right: { xs: 12, sm: 'auto' },
        width: { sm: 440 },
        p: 1.5,
        pl: 2,
        borderRadius: RADIUS.sheet,
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        ...(docked && { position: 'static', width: 'auto', flexShrink: 0, borderRadius: RADIUS.card }),
      }}
    >
      {busy ? <CircularProgress size={22} /> : <AddLocationAlt color="primary" />}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="body1" sx={{ fontWeight: 700 }}>
          {busy ? 'Sprawdzam punkt…' : 'Dotknij mapy, aby wybrać punkt'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Wybierasz {targetName(target)}
        </Typography>
      </Box>
      <Button onClick={onCancel}>Anuluj</Button>
    </Paper>
  );
}
