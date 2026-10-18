import { Box, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { TRANSIT_ACCESS_LABELS, TRANSIT_ACCESS_OPTIONS, type TransitAccess } from '../travel';

interface Props {
  value: TransitAccess;
  onChange: (value: TransitAccess) => void;
}

/** "Dojazd: Pieszo | Rowerem" of a public transport search: reach the stops on foot or by the own bike. */
export default function TransitAccessToggle({ value, onChange }: Props) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.75 }}>
      <Typography variant="caption" color="text.secondary" id="transit-access-label">
        Dojazd:
      </Typography>
      <ToggleButtonGroup
        exclusive
        size="small"
        value={value}
        aria-labelledby="transit-access-label"
        onChange={(_, v: TransitAccess | null) => v && onChange(v)}
        sx={{ '& .MuiToggleButton-root': { py: 0.25, px: 1.25, fontSize: 12 } }}
      >
        {TRANSIT_ACCESS_OPTIONS.map((a) => (
          <ToggleButton key={a} value={a}>
            {TRANSIT_ACCESS_LABELS[a]}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
}
