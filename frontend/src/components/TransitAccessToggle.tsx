import { FormControlLabel, Switch } from '@mui/material';
import DirectionsBike from '@mui/icons-material/DirectionsBike';
import type { TransitAccess } from '../travel';

interface Props {
  value: TransitAccess;
  onChange: (value: TransitAccess) => void;
}

/**
 * "Z własnym rowerem" of a public transport search (off by default): the user takes their own bike along and rides it
 * to, from and between stops, carried on transit (`access: "bike"`). On hides the accessibility choice.
 */
export default function TransitAccessToggle({ value, onChange }: Props) {
  return (
    <FormControlLabel
      sx={{ mt: 0.5, ml: 0, gap: 0.5, '& .MuiFormControlLabel-label': { fontSize: 13 } }}
      control={
        <Switch
          size="small"
          checked={value === 'bike'}
          onChange={(_, on) => onChange(on ? 'bike' : 'walk')}
          inputProps={{ 'aria-label': 'Z własnym rowerem' }}
        />
      }
      label={
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <DirectionsBike sx={{ fontSize: 16 }} /> Z własnym rowerem
        </span>
      }
    />
  );
}
