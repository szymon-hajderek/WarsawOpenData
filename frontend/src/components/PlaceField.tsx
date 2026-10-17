import { useEffect, useState } from 'react';
import {
  Autocomplete,
  Box,
  CircularProgress,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material';
import MyLocation from '@mui/icons-material/MyLocation';
import PlaceOutlined from '@mui/icons-material/PlaceOutlined';
import { searchPlaces } from '../api/geocode';
import type { Place } from '../types';
import { RADIUS } from '../layout';

interface Props {
  value: Place | null;
  onChange: (place: Place | null) => void;
  placeholder: string;
  /** Current-location place (when available), offered as the first suggestion. */
  currentLocation: Place | null;
  /** Shows a "use my location" button inside the field. */
  showLocateButton?: boolean;
  onLocate?: () => void;
}

export default function PlaceField({
  value,
  onChange,
  placeholder,
  currentLocation,
  showLocateButton,
  onLocate,
}: Props) {
  const [input, setInput] = useState(value?.label ?? '');
  const [results, setResults] = useState<Place[]>([]);
  const [loading, setLoading] = useState(false);

  // Keep the text in sync when the value changes from outside (swap, geolocation).
  useEffect(() => {
    setInput(value?.label ?? '');
  }, [value]);

  useEffect(() => {
    const q = input.trim();
    if (q.length < 3 || q === value?.label) {
      setResults([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const found = await searchPlaces(q); // Nominatim: debounce, max ~1 req/s
        if (!cancelled) setResults(found);
      } catch {
        if (!cancelled) setResults([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [input, value]);

  const typing = input.trim().length > 0 && input !== value?.label;
  const options: Place[] = [
    ...(currentLocation && !typing ? [currentLocation] : []),
    ...(typing ? results : []),
    ...(value && !typing && value.id !== currentLocation?.id ? [value] : []),
  ];

  return (
    <Autocomplete<Place, false, false, false>
      fullWidth
      size="small"
      value={value}
      inputValue={input}
      options={options}
      loading={loading}
      filterOptions={(o) => o}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      getOptionLabel={(o) => o.label}
      onInputChange={(_, text, reason) => {
        if (reason === 'input' || reason === 'clear') setInput(text);
      }}
      onChange={(_, place) => onChange(place)}
      noOptionsText={typing ? (loading ? 'Szukam…' : 'Brak wyników w Warszawie') : 'Wpisz adres lub miejsce'}
      loadingText="Szukam…"
      clearText="Wyczyść"
      openText="Otwórz"
      closeText="Zamknij"
      renderOption={(props, option) => {
        // MUI keys options by their label, which can repeat (e.g. several "Wilanowska")
        const { key: _key, ...rest } = props as typeof props & { key: string };
        return (
          <Box component="li" key={option.id} {...rest} sx={{ gap: 1.5 }}>
            {option.isCurrentLocation ? (
              <MyLocation color="primary" fontSize="small" />
            ) : (
              <PlaceOutlined color="action" fontSize="small" />
            )}
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
                {option.label}
              </Typography>
              {option.sublabel && (
                <Typography variant="caption" color="text.secondary" noWrap component="div">
                  {option.sublabel}
                </Typography>
              )}
            </Box>
          </Box>
        );
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          hiddenLabel
          variant="filled"
          placeholder={placeholder}
          slotProps={{
            htmlInput: { ...params.inputProps, 'aria-label': placeholder },
            input: {
              ...params.InputProps,
              disableUnderline: true,
              sx: { borderRadius: RADIUS.tile, fontWeight: 500 },
              endAdornment: (
                <InputAdornment position="end" sx={{ mr: -0.5 }}>
                  {loading && <CircularProgress size={16} />}
                  {showLocateButton && (
                    <IconButton size="small" aria-label="Użyj mojej lokalizacji" onClick={onLocate}>
                      <MyLocation fontSize="small" color={currentLocation ? 'primary' : 'inherit'} />
                    </IconButton>
                  )}
                  {params.InputProps.endAdornment}
                </InputAdornment>
              ),
            },
          }}
        />
      )}
    />
  );
}
