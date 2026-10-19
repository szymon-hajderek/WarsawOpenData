import { ToggleButton, ToggleButtonGroup } from '@mui/material';
import Visibility from '@mui/icons-material/Visibility';
import { Section } from './PreferenceFields';
import { setMapLook, useMapLook, type MapLook } from '../../map/mapLook';

/** How the map looks (the colour version of the map). It stays on this device. */
export default function ViewSection() {
  const [look] = useMapLook();
  return (
    <Section icon={<Visibility />} title="Widok" hint="Wygląd mapy: dotyczy mapy 2D i 3D.">
      <ToggleButtonGroup
        exclusive
        fullWidth
        size="small"
        aria-label="Wygląd mapy"
        value={look}
        onChange={(_, v: MapLook | null) => v && setMapLook(v)}
        sx={{ '& .MuiToggleButton-root': { textTransform: 'none', flexDirection: 'column', py: 1, lineHeight: 1.2 }, '& .Mui-selected': { fontWeight: 700 } }}
      >
        <ToggleButton value="flat">
          Płaska
          <small style={{ fontWeight: 400, opacity: 0.8 }}>czerwień i żółć</small>
        </ToggleButton>
        <ToggleButton value="glass">
          Szklana
          <small style={{ fontWeight: 400, opacity: 0.8 }}>liquid glass, świecąca</small>
        </ToggleButton>
      </ToggleButtonGroup>
    </Section>
  );
}
