import { Box, IconButton, Paper } from '@mui/material';
import SwapVert from '@mui/icons-material/SwapVert';
import TripOriginIcon from '@mui/icons-material/TripOrigin';
import PlaceIcon from '@mui/icons-material/Place';
import PlaceField from './PlaceField';
import type { Place } from '../types';

interface Props {
  origin: Place | null;
  destination: Place | null;
  currentLocation: Place | null;
  onOriginChange: (p: Place | null) => void;
  onDestinationChange: (p: Place | null) => void;
  onSwap: () => void;
  onLocate: () => void;
}

/** Card at the top of the screen: pick the start and the destination. */
export default function SearchCard({
  origin,
  destination,
  currentLocation,
  onOriginChange,
  onDestinationChange,
  onSwap,
  onLocate,
}: Props) {
  return (
    <Paper
      elevation={4}
      sx={{
        position: 'absolute',
        zIndex: 1000,
        top: 'calc(env(safe-area-inset-top) + 12px)',
        left: { xs: 12, sm: 16 },
        right: { xs: 12, sm: 'auto' },
        width: { sm: 440 },
        p: 1.5,
        borderRadius: '28px',
        display: 'flex',
        alignItems: 'stretch',
        gap: 1,
      }}
    >
      {/* timeline: start -> destination */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          py: 1.25,
          width: 24,
        }}
      >
        <TripOriginIcon sx={{ fontSize: 18 }} color="primary" />
        <Box
          sx={{
            flex: 1,
            my: 0.5,
            borderLeft: 2,
            borderColor: 'divider',
            borderStyle: 'dotted',
          }}
        />
        <PlaceIcon sx={{ fontSize: 20 }} color="error" />
      </Box>

      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        <PlaceField
          value={origin}
          onChange={onOriginChange}
          placeholder="Skąd jedziesz?"
          currentLocation={currentLocation}
          showLocateButton
          onLocate={onLocate}
        />
        <PlaceField
          value={destination}
          onChange={onDestinationChange}
          placeholder="Dokąd jedziesz?"
          currentLocation={currentLocation}
        />
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <IconButton
          aria-label="Zamień start z celem"
          onClick={onSwap}
          disabled={!origin && !destination}
        >
          <SwapVert />
        </IconButton>
      </Box>
    </Paper>
  );
}
