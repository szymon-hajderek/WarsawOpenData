import { Autocomplete, Box, Chip, IconButton, MenuItem, Select, TextField, Typography } from '@mui/material';
import Close from '@mui/icons-material/Close';
import PlaceOutlined from '@mui/icons-material/PlaceOutlined';
import PlaceField from '../PlaceField';
import { DISTRICTS, type AreaPoint, type ExcludedAreas } from '../../preferences/model';
import type { Place } from '../../types';

const RADII = [300, 500, 1000, 2000];
const radiusLabel = (m: number) => (m < 1000 ? `${m} m` : `${m / 1000} km`);

interface Props {
  value: ExcludedAreas;
  onChange: (next: ExcludedAreas) => void;
}

/** Areas the user does not want to pass through: Warsaw districts and own points with a radius. */
export default function AreaPicker({ value, onChange }: Props) {
  const addPoint = (place: Place | null) => {
    if (!place) return;
    const point: AreaPoint = {
      id: `${place.id}-${Date.now()}`,
      label: place.label,
      position: place.position,
      radiusM: 500,
    };
    onChange({ ...value, points: [...value.points, point] });
  };

  const patchPoint = (id: string, radiusM: number) =>
    onChange({ ...value, points: value.points.map((p) => (p.id === id ? { ...p, radiusM } : p)) });

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Autocomplete
        multiple
        size="small"
        options={[...DISTRICTS]}
        value={value.districts}
        onChange={(_, districts) => onChange({ ...value, districts })}
        noOptionsText="Brak takiej dzielnicy"
        renderTags={(tags, getTagProps) =>
          tags.map((tag, index) => {
            const { key, ...rest } = getTagProps({ index });
            return <Chip key={key} label={tag} size="small" {...rest} />;
          })
        }
        renderInput={(params) => (
          <TextField {...params} label="Dzielnice do ominięcia" placeholder={value.districts.length ? '' : 'Dodaj dzielnicę'} />
        )}
      />

      <Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 0.75 }}>
          Własne miejsca (adres + promień)
        </Typography>
        {value.points.map((p) => (
          <Box key={p.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
            <PlaceOutlined fontSize="small" color="action" />
            <Typography variant="body2" noWrap sx={{ flex: 1, minWidth: 0 }}>
              {p.label}
            </Typography>
            <Select
              size="small"
              value={p.radiusM}
              onChange={(e) => patchPoint(p.id, Number(e.target.value))}
              inputProps={{ 'aria-label': `Promień wokół: ${p.label}` }}
              sx={{ minWidth: 92 }}
            >
              {RADII.map((r) => (
                <MenuItem key={r} value={r}>
                  {radiusLabel(r)}
                </MenuItem>
              ))}
            </Select>
            <IconButton
              size="small"
              aria-label={`Usuń miejsce: ${p.label}`}
              onClick={() => onChange({ ...value, points: value.points.filter((x) => x.id !== p.id) })}
            >
              <Close fontSize="small" />
            </IconButton>
          </Box>
        ))}
        {/* remounted after every added point, so the field is empty again */}
        <PlaceField
          key={value.points.length}
          value={null}
          onChange={addPoint}
          placeholder="Dodaj miejsce do ominięcia"
          currentLocation={null}
        />
      </Box>
    </Box>
  );
}
