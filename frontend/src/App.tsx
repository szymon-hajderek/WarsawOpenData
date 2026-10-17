import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Box, Snackbar, useMediaQuery, useTheme } from '@mui/material';
import MapView, { type MapPadding } from './components/MapView';
import SearchCard from './components/SearchCard';
import RouteOptionsSheet from './components/RouteOptionsSheet';
import RouteDetailsSheet from './components/RouteDetailsSheet';
import VehicleSheet from './components/VehicleSheet';
import { useColorMode } from './colorMode';
import { fetchRouteOptions } from './api/routes';
import { BUS_POPUP_REQUEST_EVENT, detectVehicle } from './api/vehicle';
import type { LatLng, Place, Profile, RouteOption, VehicleCandidate } from './types';

type Step = 'search' | 'options' | 'route';

export default function App() {
  const { mode, toggle } = useColorMode();
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up('sm'));

  const [userPosition, setUserPosition] = useState<LatLng | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [profile, setProfile] = useState<Profile>('standard');
  const [step, setStep] = useState<Step>('search');
  const [options, setOptions] = useState<RouteOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [stepsExpanded, setStepsExpanded] = useState(false);

  // "Which vehicle am I in?" window: open from the start, can be hidden and brought back.
  const [vehicles, setVehicles] = useState<VehicleCandidate[]>([]);
  const [vehiclesLoading, setVehiclesLoading] = useState(true);
  const [vehicleOpen, setVehicleOpen] = useState(true);
  const [vehicleDismissed, setVehicleDismissed] = useState(false);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const [confirmedVehicle, setConfirmedVehicle] = useState<VehicleCandidate | null>(null);

  const currentLocation = useMemo<Place | null>(
    () =>
      userPosition
        ? { id: 'current-location', label: 'Twoja lokalizacja', position: userPosition, isCurrentLocation: true }
        : null,
    [userPosition],
  );

  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      setGeoError(true);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserPosition([pos.coords.latitude, pos.coords.longitude]),
      () => setGeoError(true),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }, []);

  useEffect(() => locate(), [locate]);

  // Detect the vehicle once after start (first location, or none after a geolocation error),
  // then only when asked through requestLinePopup().
  const [detectRun, setDetectRun] = useState(0);
  const userPositionRef = useRef(userPosition);
  userPositionRef.current = userPosition;

  useEffect(() => {
    if (userPosition || geoError) setDetectRun((n) => n || 1);
  }, [userPosition, geoError]);

  useEffect(() => {
    const onRequest = () => {
      setDetectRun((n) => n + 1);
      setVehicleDismissed(false);
      setVehicleOpen(true);
    };
    window.addEventListener(BUS_POPUP_REQUEST_EVENT, onRequest);
    return () => window.removeEventListener(BUS_POPUP_REQUEST_EVENT, onRequest);
  }, []);

  useEffect(() => {
    if (detectRun === 0) return;
    let cancelled = false;
    setVehiclesLoading(true);
    detectVehicle(userPositionRef.current)
      .then((found) => {
        if (cancelled) return;
        setVehicles(found);
        setSelectedVehicleId((prev) => (found.some((v) => v.id === prev) ? prev : found[0]?.id ?? null));
      })
      .finally(() => !cancelled && setVehiclesLoading(false));
    return () => {
      cancelled = true;
    };
  }, [detectRun]);

  // The start defaults to the user's location.
  useEffect(() => {
    if (currentLocation) setOrigin((prev) => prev ?? currentLocation);
  }, [currentLocation]);

  // Fetch connections as soon as both points are set (and when the profile changes).
  useEffect(() => {
    if (!origin || !destination) {
      setOptions([]);
      setSelectedId(null);
      setChosenId(null);
      setStep('search');
      return;
    }
    let cancelled = false;
    setStep('options');
    setChosenId(null);
    setLoading(true);
    fetchRouteOptions(origin, destination, profile)
      .then((result) => {
        if (cancelled) return;
        setOptions(result);
        setSelectedId(result[0]?.id ?? null);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [origin, destination, profile]);

  const handleLocateOrigin = () => {
    if (currentLocation) setOrigin(currentLocation);
    else locate();
  };

  const swap = () => {
    setOrigin(destination);
    setDestination(origin);
  };

  const chosen = options.find((o) => o.id === chosenId) ?? null;
  const preview = step === 'route' ? chosen : step === 'options' ? options.find((o) => o.id === selectedId) ?? null : null;

  // Parts of the map covered by the panels, so the route stays in the visible area.
  const padding: MapPadding = desktop
    ? { top: 60, left: 500, bottom: 60, right: 90 }
    : { top: step === 'route' ? 100 : 190, left: 40, bottom: step === 'route' ? (stepsExpanded ? 450 : 380) : 400, right: 70 };

  return (
    <Box sx={{ position: 'fixed', inset: 0, bgcolor: 'background.default' }}>
      <MapView
        paletteMode={mode}
        onToggleMode={toggle}
        userPosition={userPosition}
        onLocate={locate}
        origin={origin}
        destination={destination}
        route={preview}
        detailed={step === 'route'}
        padding={padding}
      />

      {step !== 'route' && (
        <SearchCard
          origin={origin}
          destination={destination}
          currentLocation={currentLocation}
          onOriginChange={setOrigin}
          onDestinationChange={setDestination}
          onSwap={swap}
          onLocate={handleLocateOrigin}
        />
      )}

      {step === 'search' && !vehicleDismissed && (
        <VehicleSheet
          candidates={vehicles}
          loading={vehiclesLoading}
          open={vehicleOpen}
          selectedId={selectedVehicleId}
          confirmed={confirmedVehicle}
          onOpenChange={setVehicleOpen}
          onSelect={setSelectedVehicleId}
          onConfirm={() => {
            setConfirmedVehicle(vehicles.find((v) => v.id === selectedVehicleId) ?? null);
            setVehicleOpen(false);
          }}
          onDismiss={() => setVehicleDismissed(true)}
        />
      )}

      {step === 'options' && (
        <RouteOptionsSheet
          options={options}
          loading={loading}
          selectedId={selectedId}
          profile={profile}
          onSelect={setSelectedId}
          onProfileChange={setProfile}
          onConfirm={() => {
            setChosenId(selectedId);
            setStep('route');
          }}
        />
      )}

      {step === 'route' && chosen && origin && destination && (
        <RouteDetailsSheet
          route={chosen}
          origin={origin}
          destination={destination}
          expanded={stepsExpanded}
          onExpandedChange={setStepsExpanded}
          onBack={() => setStep('options')}
        />
      )}

      <Snackbar
        open={geoError}
        autoHideDuration={6000}
        onClose={() => setGeoError(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        sx={{ top: { xs: 150 } }}
      >
        <Alert severity="info" variant="filled" onClose={() => setGeoError(false)}>
          Nie udało się ustalić lokalizacji. Wpisz punkt startowy ręcznie.
        </Alert>
      </Snackbar>
    </Box>
  );
}
