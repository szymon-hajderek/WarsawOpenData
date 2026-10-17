import type { ReactNode } from 'react';
import { Box, Paper } from '@mui/material';
import { PANEL_BOTTOM } from '../layout';

interface Props {
  children: ReactNode;
  /** Makes the handle clickable (collapse / expand the sheet). */
  onHandleClick?: () => void;
  maxHeight?: string | Record<string, string>;
}

/** Floating panel at the bottom (mobile) or on the left side (desktop). */
export default function Sheet({ children, onHandleClick, maxHeight }: Props) {
  return (
    <Paper
      elevation={8}
      sx={{
        position: 'absolute',
        zIndex: 1000,
        bottom: PANEL_BOTTOM,
        left: { xs: 8, sm: 16 },
        right: { xs: 8, sm: 'auto' },
        width: { sm: 440 },
        maxHeight: maxHeight ?? { xs: '46vh', sm: 'calc(100vh - 200px)' },
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '28px',
        overflow: 'hidden',
      }}
    >
      <Box
        onClick={onHandleClick}
        role={onHandleClick ? 'button' : undefined}
        aria-label={onHandleClick ? 'Zwiń lub rozwiń panel' : undefined}
        sx={{ py: 1.25, display: 'grid', placeItems: 'center', cursor: onHandleClick ? 'pointer' : 'default' }}
      >
        <Box sx={{ width: 36, height: 4, borderRadius: 2, bgcolor: 'text.disabled', opacity: 0.5 }} />
      </Box>
      {children}
    </Paper>
  );
}
