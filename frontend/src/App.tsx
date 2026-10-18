import { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, Snackbar, Typography, useMediaQuery, useTheme } from '@mui/material';
import MapView, { type MapPadding } from './components/MapView';
import SearchCard from './components/SearchCard';
import RouteOptionsSheet from './components/RouteOptionsSheet';
import RouteDetailsSheet from './components/RouteDetailsSheet';
import VehicleSheet from './components/VehicleSheet';
import { useSnapHeights, type SheetSnap } from './components/SnapSheet';
import BottomNav, { type Tab } from './components/BottomNav';
import PreferencesPage from './components/PreferencesPage';
import DemoPage from './components/DemoPage';
import { simState } from './api/sim';
import FilterSheet from './components/FilterSheet';
import { useColorMode } from './colorMode';
import { requestLinePopup } from './api/vehicle';
import { geoErrorText, useLocationTrack } from './hooks/useLocationTrack';
import { useRouteSearch } from './hooks/useRouteSearch';
import type { TravelMode } from './travel';
import { departureSummary, departureWhen, type Departure } from './utils/departure';
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
import type { Place, StopOrder } from './types';

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
  // Departure time of the search: `null` = now (not saved, so a reload starts from now again).
  const [departure, setDeparture] = useState<Departure>(null);
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

  // "Which vehicle am I in?" window: open from the start, can be hidden and brought back.
  const vehicle = useVehicleDetection({ position: userPosition, geoError, getTrack });

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

  const { options, loading, error: searchError, offline: routesOffline, errorMessage } = useRouteSearch({
    origin,
    destination,
    via,
    order: stopOrder,
    search,
    travel,
    when: departureWhen(departure),
  });

  // A new search starts clean: no filters, no chosen route.
  useEffect(() => {
    setFilters(DEFAULT_FILTERS);
    setPickedId(null);
    setChosenId(null);
  }, [origin, destination, via, stopOrder, travel, departure]);

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

  const preview = step === 'route' ? chosen : step === 'options' ? visible.find((o) => o.id === selectedId) ?? null : null;

  // Parts of the map covered by the panels, so the route stays in the visible area.
  const padding: MapPadding = desktop
    ? MAP_PADDING.desktop
    : {
        top: step === 'route' ? 100 : 190,
        left: 40,
        // keep the route visible above the sheet at its current height
        bottom: BOTTOM_NAV_HEIGHT + 40 + (step === 'route' ? detailsHeights[detailsSnap] : step === 'options' ? optionsHeights[optionsSnap] : 260),
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
          origin={origin}
          destination={destination}
          route={preview}
          detailed={step === 'route'}
          padding={padding}
          stops={via}
          controlsOffset={step === 'route' ? 0 : 84 + stopFields.length * 56}
          onDetectVehicle={step === 'search' ? requestLinePopup : undefined}
        />

        {step !== 'route' && (
          <SearchCard
            origin={origin}
            destination={destination}
            stops={stopFields}
            order={stopOrder}
            travel={travel}
            onTravelChange={setTravel}
            departure={departure}
            onDepartureChange={setDeparture}
            currentLocation={currentLocation}
            onOriginChange={setOrigin}
            onDestinationChange={setDestination}
            onStopsChange={setStopFields}
            onOrderChange={setStopOrder}
            onSwap={swap}
            onLocate={handleLocateOrigin}
          />
        )}

        {step === 'search' && !vehicle.dismissed && (
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

        {step === 'options' && (
          <RouteOptionsSheet
            options={visible}
            departure={departureSummary(departure)}
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
            onConfirm={() => setChosenId(selectedId)}
          />
        )}

        {step === 'route' && chosen && origin && destination && (
          <RouteDetailsSheet
            route={chosen}
            origin={origin}
            destination={destination}
            snap={detailsSnap}
            onSnapChange={setDetailsSnap}
            onBack={() => setChosenId(null)}
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

      {tracker.status === 'tracking' && step !== 'route' && (
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
    </Box>
  );
}
