import { BottomNavigation, BottomNavigationAction, Paper } from '@mui/material';
import MapOutlined from '@mui/icons-material/MapOutlined';
import Tune from '@mui/icons-material/Tune';
import Science from '@mui/icons-material/Science';
import { BOTTOM_NAV_HEIGHT, PANEL_WIDTH, RADIUS } from '../layout';

export type Tab = 'map' | 'preferences' | 'demo';

/** Bottom navigation bar: Map and Preferences tabs, and Demo when the backend runs in simulation mode. */
export default function BottomNav({ tab, onChange, demo = false }: { tab: Tab; onChange: (tab: Tab) => void; demo?: boolean }) {
  return (
    <Paper
      elevation={8}
      component="nav"
      aria-label="Główna nawigacja"
      sx={{
        position: 'fixed',
        left: 0,
        // a wide screen: under the side panel only, the map goes down to the bottom edge
        right: { xs: 0, sm: 'auto' },
        width: { sm: PANEL_WIDTH.sm, md: PANEL_WIDTH.md },
        bottom: 0,
        zIndex: 1200,
        pb: 'env(safe-area-inset-bottom)',
        borderTopLeftRadius: RADIUS.sheet,
        borderTopRightRadius: RADIUS.sheet,
        overflow: 'hidden',
      }}
    >
      <BottomNavigation
        showLabels
        value={tab}
        onChange={(_, v: Tab) => onChange(v)}
        sx={{ height: BOTTOM_NAV_HEIGHT, bgcolor: 'transparent', maxWidth: 640, mx: 'auto' }}
      >
        <BottomNavigationAction value="map" label="Mapa" icon={<MapOutlined />} />
        <BottomNavigationAction value="preferences" label="Preferencje" icon={<Tune />} />
        {demo && <BottomNavigationAction value="demo" label="Demo" icon={<Science />} />}
      </BottomNavigation>
    </Paper>
  );
}
