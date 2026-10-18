import { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Snackbar, Typography, useMediaQuery, useTheme } from '@mui/material';
import MapView, { type MapPadding } from './components/MapView';
import SearchCard from './components/SearchCard';
import RouteOptionsSheet from './components/RouteOptionsSheet';
import RouteDetailsSheet from './components/RouteDetailsSheet';
import VehicleSheet from './components/VehicleSheet';
import ActiveTripSheet from './components/ActiveTripSheet';
import { useSnapHeights, type SheetSnap } from './components/SnapSheet';
import BottomNav, { type Tab } from './components/BottomNav';
import PreferencesPage from './components/PreferencesPage';
import DemoPage from './components/DemoPage';
import { simState } from './api/sim';
import FilterSheet from './components/FilterSheet';
import { useColorMode } from './colorMode';
import { detectionPoints, requestLinePopup } from './api/vehicle';
import { geoErrorText, useLocationTrack } from './hooks/useLocationTrack';
import { useRouteSearch } from './hooks/useRouteSearch';
import { useTripProgress } from './hooks/useTripProgress';
import type { TravelMode } from './travel';
import { useVehicleDetection } from './hooks/useVehicleDetection';
import { usePreferences } from './preferences/PreferencesProvider';
import { useHistory } from './history/HistoryProvider';
import {
  applyListFilters,
  applyOverrides,
  clearFilter,
  DEFAULT_FILTERS,
  filterChips,
  routeSearchBody,
  summarize,
  type TripFilters,
} from './preferences/model';
import { BOTTOM_NAV_HEIGHT, MAP_PADDING } from './layout';
import type { Place, RouteOption, StopOrder } from './types';

/** Origin id prefix of "plan from the vehicle I am in" (`onboard` in `POST /api/routes`). */
const ONBOARD_PREFIX = 'onboard:';

/** The active trip ("Rozpocznij przejazd" ... "Zakończ"): the route being travelled and its ends. */
interface ActiveTrip {
  route: RouteOption;
  origin: Place;
  destination: Place;
}

type Step = 'search' | 'options' | 'route';

export default function App() {
  const { mode, toggle } = useColorMode();
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up('sm'));

  const { position: userPosition, geoError, clearGeoError, locate, getTrack } = useLocationTrack();
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  // Intermediate stops (`null` = an empty field the user has just added) and how they are ordered.
  const [stopFields, setStopFields] = useState<(Place | null)[]>([]);
  const [stopOrder, setStopOrder] = useState<StopOrder>('given');
  // Public transport (default) or a street-only trip: walking, wheelchair, stroller, own bike.
  const [travel, setTravel] = useState<TravelMode>('transit');
  const [tab, setTab] = useState<Tab>('map');
  // The Demo tab exists only when the backend runs in simulation mode (SIM_SCENARIO).
  const [simulation, setSimulation] = useState(false);
  useEffect(() => {
    void simState().then((s) => setSimulation(s !== null));
  }, []);
  const { effective, activeRule } = usePreferences();
  const { tracker } = useHistory();
  // Filters apply to the current search only; they start from the saved preferences.
  const [filters, setFilters] = useState<TripFilters>(DEFAULT_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [chosenId, setChosenId] = useState<string | null>(null);
  // Heights of the route list and of the route details (bar / middle / full), reset when the screen changes.
  const [optionsSnap, setOptionsSnap] = useState<SheetSnap>('middle');
  const [detailsSnap, setDetailsSnap] = useState<SheetSnap>('middle');
  const optionsHeights = useSnapHeights(352);
  const detailsHeights = useSnapHeights(292);

  // Active trip mode, and the search for a new destination / route inside it.
  const [activeTrip, setActiveTrip] = useState<ActiveTrip | null>(null);
  const [replanning, setReplanning] = useState(false);
  const [tripSnap, setTripSnap] = useState<SheetSnap>('middle');
  const [tripVehicleOpen, setTripVehicleOpen] = useState(false);
  const [onboardNotice, setOnboardNotice] = useState(false);
  const tripHeights = useSnapHeights(300);

  // "Which vehicle am I in?" window: open from the start, can be hidden and brought back. In the active trip it
  // detects from the trip's own track (the recorder's points), else from the last 1-3 positions.
  const tripTrack = () => {
    const points = activeTrip ? detectionPoints(tracker.track()) : [];
    return points.length > 0 ? points : getTrack();
  };
  const vehicle = useVehicleDetection({ position: userPosition, geoError, getTrack: tripTrack });
  const progress = useTripProgress(activeTrip?.route ?? null, userPosition);

  const currentLocation = useMemo<Place | null>(
    () =>
      userPosition
        ? { id: 'current-location', label: 'Twoja lokalizacja', position: userPosition, isCurrentLocation: true }
        : null,
    [userPosition],
  );

  // The start defaults to the user's location.
  useEffect(() => {
    if (currentLocation) setOrigin((prev) => prev ?? currentLocation);
  }, [currentLocation]);

  // Only the stops that are filled in go into the search; the key keeps empty fields from refetching.
  const viaKey = stopFields.map((p) => p?.id ?? '').join('|');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const via = useMemo(() => stopFields.filter((p): p is Place => p !== null), [viaKey]);
  const trip = useMemo(() => applyOverrides(effective, filters.overrides), [effective, filters.overrides]);
  // The vehicle chips of the filters override the preference's excluded modes for this search.
  const search = useMemo(() => routeSearchBody(trip, filters.modes), [trip, filters.modes]);

  const onboardVehicleId = origin?.id.startsWith(ONBOARD_PREFIX) ? origin.id.slice(ONBOARD_PREFIX.length) : null;
  const { options, loading, error: searchError, offline: routesOffline, errorMessage, vehicleNotFound } = useRouteSearch({
    origin,
    destination,
    via,
    order: stopOrder,
    search,
    travel,
    onboardVehicleId,
  });

  // The backend does not know the vehicle (404): plan from the GPS position instead, with a short note.
  useEffect(() => {
    if (!vehicleNotFound || !origin?.id.startsWith(ONBOARD_PREFIX)) return;
    setOrigin(currentLocation ?? { id: 'current-location', label: 'Twoja lokalizacja', position: origin.position, isCurrentLocation: true });
    setOnboardNotice(true);
  }, [vehicleNotFound, origin, currentLocation]);

  // A new search starts clean: no filters, no chosen route.
  useEffect(() => {
    setFilters(DEFAULT_FILTERS);
    setPickedId(null);
    setChosenId(null);
  }, [origin, destination, via, stopOrder, travel]);

  // The backend is switched off or could not be reached: say so each time it happens (no made-up data is shown).
  const offlineShown = routesOffline || vehicle.offline;
  const [offlineNoticeOpen, setOfflineNoticeOpen] = useState(false);
  useEffect(() => {
    if (offlineShown) setOfflineNoticeOpen(true);
  }, [offlineShown]);


  const handleLocateOrigin = () => {
    if (currentLocation) setOrigin(currentLocation);
    else locate();
  };

  // Reverses the whole trip: start <-> destination and the stops in reverse order.
  const swap = () => {
    setOrigin(destination);
    setDestination(origin);
    setStopFields((prev) => [...prev].reverse());
  };

  // Preferences of this search = the ones valid now + this search's overrides.
  // Filters and sorting are about transit options; a street trip is a single path.
  const visible = useMemo(
    () => (travel === 'transit' ? applyListFilters(options, trip, filters) : options),
    [options, trip, filters, travel],
  );
  const chips = useMemo(() => filterChips(filters, trip), [filters, trip]);

  // The selection always points into the filtered list.
  const selectedId = visible.some((o) => o.id === pickedId) ? pickedId : visible[0]?.id ?? null;

  const chosen = options.find((o) => o.id === chosenId) ?? null;
  const step: Step = !origin || !destination ? 'search' : chosen ? 'route' : 'options';
  // A sheet opens at its middle height each time its step starts.
  useEffect(() => {
    if (step === 'options') setOptionsSnap('middle');
    if (step === 'route') setDetailsSnap('middle');
  }, [step]);

  // What is on the screen: the active trip (unless a new route is being searched) or the normal flow.
  const inTrip = activeTrip !== null && !replanning;

  const startTrip = () => {
    if (!chosen || !origin || !destination) return;
    setActiveTrip({ route: chosen, origin, destination });
    setReplanning(false);
    setTripSnap('middle');
  };

  const endTrip = () => {
    void tracker.stop(); // saves the pace recording, as before
    setActiveTrip(null);
    setReplanning(false);
    setTripVehicleOpen(false);
  };

  /** "Zmień cel" / "Zmień trasę": the full search card; the start = the confirmed vehicle, else the GPS position. */
  const replan = (keepDestination: boolean) => {
    if (!activeTrip) return;
    const here = userPosition ?? activeTrip.origin.position;
    const v = vehicle.confirmed;
    setOrigin(
      v && !v.manual
        ? { id: `${ONBOARD_PREFIX}${v.id}`, label: `Z pojazdu: ${v.line} (następne przystanki)`, position: here }
        : currentLocation ?? { id: 'current-location', label: 'Twoja lokalizacja', position: here, isCurrentLocation: true },
    );
    setDestination(keepDestination ? activeTrip.destination : null);
    setStopFields([]);
    setTravel('transit');
    setTripVehicleOpen(false);
    setReplanning(true);
  };

  const confirmOption = () => {
    if (activeTrip && replanning) {
      const picked = visible.find((o) => o.id === selectedId);
      if (!picked || !origin || !destination) return;
      // The new route replaces the old one; the trip (and its recording) goes on.
      setActiveTrip({ route: picked, origin, destination });
      setReplanning(false);
      setTripSnap('middle');
      return;
    }
    setChosenId(selectedId);
  };

  const detectInTrip = () => {
    setTripVehicleOpen(true);
    vehicle.redetect();
  };

  const preview = inTrip ? activeTrip.route : step === 'route' ? chosen : step === 'options' ? visible.find((o) => o.id === selectedId) ?? null : null;

  // Parts of the map covered by the panels, so the route stays in the visible area.
  const padding: MapPadding = desktop
    ? MAP_PADDING.desktop
    : {
        top: inTrip ? 40 : step === 'route' ? 100 : 190,
        left: 40,
        // keep the route visible above the sheet at its current height
        bottom:
          BOTTOM_NAV_HEIGHT +
          40 +
          (inTrip ? tripHeights[tripSnap] : step === 'route' ? detailsHeights[detailsSnap] : step === 'options' ? optionsHeights[optionsSnap] : 260),
        right: 70,
      };

  return (
    <Box sx={{ position: 'fixed', inset: 0, bgcolor: 'background.default' }}>
      {/* Under the Preferences page the map and panels cannot take focus or be read by a screen reader. */}
      <Box
        {...(tab !== 'map' ? ({ inert: '' } as object) : {})}
        sx={tab === 'demo' ? { visibility: 'hidden' } : undefined}
      >
        <MapView
          paletteMode={mode}
          onToggleMode={toggle}
          userPosition={userPosition}
          onLocate={locate}
          origin={inTrip ? activeTrip.origin : origin}
          destination={inTrip ? activeTrip.destination : destination}
          route={preview}
          detailed={inTrip || step === 'route'}
          padding={padding}
          stops={inTrip ? [] : via}
          controlsOffset={inTrip || step === 'route' ? 0 : 84 + stopFields.length * 56}
          onDetectVehicle={!activeTrip && step === 'search' ? requestLinePopup : undefined}
          follow={inTrip}
        />

        {!inTrip && step !== 'route' && (
          <SearchCard
            origin={origin}
            destination={destination}
            stops={stopFields}
            order={stopOrder}
            travel={travel}
            onTravelChange={setTravel}
            currentLocation={currentLocation}
            onOriginChange={setOrigin}
            onDestinationChange={setDestination}
            onStopsChange={setStopFields}
            onOrderChange={setStopOrder}
            onSwap={swap}
            onLocate={handleLocateOrigin}
            onBackToTrip={replanning ? () => setReplanning(false) : undefined}
          />
        )}

        {!activeTrip && step === 'search' && !vehicle.dismissed && (
          <VehicleSheet
            candidates={vehicle.vehicles}
            lines={vehicle.lines}
            manual={vehicle.manual}
            loading={vehicle.loading}
            offline={vehicle.offline}
            snap={vehicle.snap}
            selectedId={vehicle.selectedId}
            confirmed={vehicle.confirmed}
            onSnapChange={vehicle.setSnap}
            onSelect={vehicle.setSelectedId}
            onManualLine={vehicle.selectManualLine}
            onClearManual={vehicle.clearManual}
            onRedetect={vehicle.redetect}
            onConfirm={vehicle.confirm}
            onDismiss={vehicle.dismiss}
          />
        )}

        {inTrip && (
          <ActiveTripSheet
            route={activeTrip.route}
            progress={progress}
            elapsedS={tracker.elapsedS}
            vehicle={vehicle.confirmed}
            snap={tripSnap}
            onSnapChange={setTripSnap}
            onDetectVehicle={detectInTrip}
            onChangeDestination={() => replan(false)}
            onReroute={() => replan(true)}
            onEnd={endTrip}
          />
        )}

        {inTrip && tripVehicleOpen && !vehicle.dismissed && (
          <VehicleSheet
            candidates={vehicle.vehicles}
            lines={vehicle.lines}
            manual={vehicle.manual}
            loading={vehicle.loading}
            offline={vehicle.offline}
            snap={vehicle.snap}
            selectedId={vehicle.selectedId}
            confirmed={vehicle.confirmed}
            onSnapChange={vehicle.setSnap}
            onSelect={vehicle.setSelectedId}
            onManualLine={vehicle.selectManualLine}
            onClearManual={vehicle.clearManual}
            onRedetect={vehicle.redetect}
            onConfirm={() => {
              vehicle.confirm();
              setTripVehicleOpen(false);
            }}
            onDismiss={() => {
              vehicle.dismiss();
              setTripVehicleOpen(false);
            }}
          />
        )}

        {!inTrip && step === 'options' && (
          <RouteOptionsSheet
            options={visible}
            foundCount={options.length}
            loading={loading}
            error={searchError}
            errorMessage={errorMessage}
            offline={routesOffline}
            selectedId={selectedId}
            summary={summarize(trip)}
            activeRule={activeRule}
            chips={chips}
            snap={optionsSnap}
            onSnapChange={setOptionsSnap}
            onSelect={setPickedId}
            onOpenFilters={() => setFiltersOpen(true)}
            onClearChip={(id) => setFilters((f) => clearFilter(f, id))}
            onClearAll={() => setFilters(DEFAULT_FILTERS)}
            onConfirm={confirmOption}
          />
        )}

        {!activeTrip && step === 'route' && chosen && origin && destination && (
          <RouteDetailsSheet
            route={chosen}
            origin={origin}
            destination={destination}
            snap={detailsSnap}
            onSnapChange={setDetailsSnap}
            onBack={() => setChosenId(null)}
            onStart={startTrip}
          />
        )}

        <FilterSheet
          open={filtersOpen}
          onClose={() => setFiltersOpen(false)}
          filters={filters}
          onChange={setFilters}
          effective={effective}
          trip={trip}
          resultCount={visible.length}
        />

      </Box>

      {tracker.status === 'tracking' && !activeTrip && step !== 'route' && (
        <Box
          sx={{
            position: 'fixed',
            zIndex: 1150,
            left: '50%',
            transform: 'translateX(-50%)',
            bottom: `calc(env(safe-area-inset-bottom) + ${BOTTOM_NAV_HEIGHT + 8}px)`,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            pl: 2,
            pr: 0.75,
            py: 0.5,
            borderRadius: 999,
            bgcolor: 'error.main',
            color: 'error.contrastText',
            boxShadow: 6,
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 700 }}>
            ● Zapisuję przejazd · {Math.floor(tracker.elapsedS / 60)}:{String(tracker.elapsedS % 60).padStart(2, '0')}
          </Typography>
          <Button size="small" variant="contained" color="inherit" sx={{ color: 'error.main', py: 0.25 }} onClick={() => void tracker.stop()}>
            Zakończ
          </Button>
        </Box>
      )}

      {tab === 'preferences' && <PreferencesPage />}
      {tab === 'demo' && <DemoPage paletteMode={mode} onToggleMode={toggle} />}
      <BottomNav tab={tab} onChange={setTab} demo={simulation} />

      <Snackbar
        open={geoError}
        autoHideDuration={6000}
        onClose={clearGeoError}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        sx={{ top: { xs: 150 } }}
      >
        <Alert severity="info" variant="filled" onClose={clearGeoError}>
          {geoErrorText()}
        </Alert>
      </Snackbar>

      <Snackbar
        open={offlineNoticeOpen}
        autoHideDuration={8000}
        onClose={() => setOfflineNoticeOpen(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        sx={{ top: { xs: 150 } }}
      >
        <Alert severity="error" variant="filled" onClose={() => setOfflineNoticeOpen(false)}>
          Nie połączono z serwerem. Sprawdź, czy backend działa.
        </Alert>
      </Snackbar>

      <Snackbar
        open={onboardNotice}
        autoHideDuration={6000}
        onClose={() => setOnboardNotice(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        sx={{ top: { xs: 150 } }}
      >
        <Alert severity="info" variant="filled" onClose={() => setOnboardNotice(false)}>
          Nie znaleziono pojazdu. Planuję od Twojej lokalizacji.
        </Alert>
      </Snackbar>
    </Box>
  );
}
