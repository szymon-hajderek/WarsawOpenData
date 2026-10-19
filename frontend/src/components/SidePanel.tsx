import type { ReactNode } from 'react';
import { Box } from '@mui/material';
import { SheetDock } from './SnapSheet';
import { BOTTOM_NAV_HEIGHT, PANEL_WIDTH } from '../layout';

/**
 * Wide screens (from `sm`, 600 px): the search card and the sheets stacked in one scrollable column on the left,
 * above the navigation bar; the map fills the rest. On a phone (`on` false) the children float as before.
 */
export default function SidePanel({ on, children }: { on: boolean; children: ReactNode }) {
  if (!on) return <>{children}</>;
  return (
    <Box
      component="aside"
      aria-label="Panel wyszukiwania"
      sx={{
        position: 'absolute',
        zIndex: 1000,
        top: 0,
        left: 0,
        bottom: `calc(env(safe-area-inset-bottom) + ${BOTTOM_NAV_HEIGHT}px)`,
        width: PANEL_WIDTH,
        overflowY: 'auto',
        overscrollBehavior: 'contain',
        bgcolor: 'background.default',
        borderRight: 1,
        borderColor: 'divider',
        p: 1.5,
        pt: 'calc(env(safe-area-inset-top) + 12px)',
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
      }}
    >
      <SheetDock.Provider value>{children}</SheetDock.Provider>
    </Box>
  );
}
