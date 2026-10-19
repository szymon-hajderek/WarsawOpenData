import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Autocomplete,
  Box,
  CircularProgress,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material';
import History from '@mui/icons-material/History';
import MyLocation from '@mui/icons-material/MyLocation';
import PlaceOutlined from '@mui/icons-material/PlaceOutlined';
import AddLocationAlt from '@mui/icons-material/AddLocationAlt';
import { MIN_QUERY, searchPlaces } from '../api/geocode';
import { topPlaces } from '../places/frequentPlaces';
import { useFrequentPlaces } from '../places/FrequentPlacesProvider';
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
  autoFocus?: boolean;
  /** Offers "Wybierz na mapie" in the list: the place is then picked by tapping the map. */
  onPickOnMap?: () => void;
}

/** The "Wybierz na mapie" entry of the list (never a real place). */
const PICK_ON_MAP: Place = { id: 'pick-on-map', label: 'Wybierz na mapie', position: [0, 0] };

export default function PlaceField({
  value,
  onChange,
  placeholder,
  currentLocation,
  showLocateButton,
  onLocate,
  autoFocus,
  onPickOnMap,
}: Props) {
  const [input, setInput] = useState(value?.label ?? '');
  const [results, setResults] = useState<Place[]>([]);
  const [loading, setLoading] = useState(false);
  // The position only orders results; a new fix must not restart a search in progress.
  const nearRef = useRef(currentLocation?.position);
  nearRef.current = currentLocation?.position;

  // Keep the text in sync when the value changes from outside (swap, geolocation).
  useEffect(() => {
    setInput(value?.label ?? '');
  }, [value]);

  useEffect(() => {
    const q = input.trim();
    if (q.length < MIN_QUERY || q === value?.label) {
      setResults([]);
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        // Our own places arrive first (a few ms), Nominatim's are merged in later (searchPlaces waits for it).
        const found = await searchPlaces(q, ac.signal, nearRef.current, (local) => {
          if (!ac.signal.aborted) setResults(local);
        });
        if (!ac.signal.aborted) setResults(found);
      } catch {
        if (!ac.signal.aborted) setResults([]);
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    }, 150);
    return () => {
      ac.abort(); // also cancels the request that is already on its way
      clearTimeout(timer);
    };
  }, [input, value]);

  const typing = input.trim().length > 0 && input !== value?.label;
  const { places: frequentList } = useFrequentPlaces();
  // Frequent places come first: up to 3 in an empty field, the matching ones while typing.
  const frequent = useMemo(
    () => topPlaces(frequentList, Date.now(), 3, typing ? input.trim() : undefined),
    [frequentList, typing, input],
  );
  const frequentIds = new Set(frequent.map((p) => p.id));
  const options: Place[] = [
    ...(currentLocation && !typing ? [currentLocation] : []),
    ...frequent.filter((p) => p.id !== currentLocation?.id && (typing || p.id !== value?.id)),
    ...(typing ? results.filter((p) => !frequentIds.has(p.id)) : []),
    ...(value && !typing && value.id !== currentLocation?.id ? [value] : []),
    ...(onPickOnMap && !typing ? [PICK_ON_MAP] : []),
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
      onChange={(_, place) => (place?.id === PICK_ON_MAP.id ? onPickOnMap?.() : onChange(place))}
      // Leaving the field without a choice puts the chosen place back, so text and value never disagree.
      onClose={(_, reason) => {
        if (reason === 'blur' || reason === 'escape') setInput(value?.label ?? '');
      }}
      noOptionsText={
        typing
          ? loading
            ? 'Szukam…'
            : input.trim().length < 3
              ? 'Brak przystanków. Wpisz co najmniej 3 znaki, aby szukać adresów.'
              : 'Brak wyników w Warszawie'
          : 'Wpisz adres lub miejsce'
      }
      loadingText="Szukam…"
      clearText="Wyczyść"
      openText="Otwórz"
      closeText="Zamknij"
      renderOption={(props, option) => {
        // MUI keys options by their label, which can repeat (e.g. several "Wilanowska")
        const { key: _key, ...rest } = props as typeof props & { key: string };
        return (
          <Box component="li" key={option.id} {...rest} sx={{ gap: 1.5 }}>
            {option.id === PICK_ON_MAP.id ? (
              <AddLocationAlt color="primary" fontSize="small" />
            ) : option.isCurrentLocation ? (
              <MyLocation color="primary" fontSize="small" />
            ) : frequentIds.has(option.id) ? (
              <History color="action" fontSize="small" />
            ) : (
              <PlaceOutlined color="action" fontSize="small" />
            )}
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
                {option.label}
              </Typography>
              {(option.sublabel || frequentIds.has(option.id)) && (
                <Typography variant="caption" color="text.secondary" noWrap component="div">
                  {frequentIds.has(option.id)
                    ? ['Często wybierane', option.sublabel].filter(Boolean).join(' · ')
                    : option.sublabel}
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
          // eslint-disable-next-line jsx-a11y/no-autofocus -- the field is added by the user's own click
          autoFocus={autoFocus}
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
