import { BottomNavigation, BottomNavigationAction, Paper } from '@mui/material';
import MapOutlined from '@mui/icons-material/MapOutlined';
import Tune from '@mui/icons-material/Tune';
import { BOTTOM_NAV_HEIGHT, RADIUS } from '../layout';

export type Tab = 'map' | 'preferences';

/** Bottom navigation bar: Map and Preferences tabs. */
export default function BottomNav({ tab, onChange }: { tab: Tab; onChange: (tab: Tab) => void }) {
  return (
    <Paper
      elevation={8}
      component="nav"
      aria-label="Główna nawigacja"
      sx={{
        position: 'fixed',
        left: 0,
        right: 0,
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
      </BottomNavigation>
    </Paper>
  );
}
