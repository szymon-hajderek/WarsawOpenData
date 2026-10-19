import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Box, Button, Snackbar, Typography, useMediaQuery, useTheme } from '@mui/material';
import MapView, { type MapPadding } from './components/MapView';
import { useMap3d } from './map/map3d';
import SearchCard, { type PickTarget } from './components/SearchCard';
import PickBanner from './components/PickBanner';
import { placeAt } from './api/pickPlace';
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
import SidePanel from './components/SidePanel';
import { useColorMode } from './colorMode';
import { detectionPoints } from './api/vehicle';
import { geoErrorText, useLocationTrack } from './hooks/useLocationTrack';
import { useHeading } from './hooks/useHeading';
import { useRouteSearch } from './hooks/useRouteSearch';
import { useTripProgress } from './hooks/useTripProgress';
import { countdownText, mustWait, secondsUntil, tripStartAt } from './utils/tripStart';
import { hasAccess, type Access, type TransitAccess, type TravelMode } from './travel';
import { departureSummary, departureWhen, type Departure } from './utils/departure';
import { useVehicleDetection } from './hooks/useVehicleDetection';
import { usePreferences } from './preferences/PreferencesProvider';
import { useHistory } from './history/HistoryProvider';
import { useFrequentPlaces } from './places/FrequentPlacesProvider';
import {
  applyListFilters,
  applyOverrides,
  clearFilter,
  DEFAULT_FILTERS,
  filterChips,
  type FilterChip,
  routeSearchBody,
  summarize,
  type TripFilters,
} from './preferences/model';
import { BOTTOM_NAV_HEIGHT, MAP_PADDING, PANEL_WIDTH } from './layout';
import type { LatLng, Place, RouteOption, StopOrder, VehicleCandidate } from './types';

// The 3D map prototype is loaded only when it is switched on (MapLibre GL is big).
const MapView3D = lazy(() => import('./components/MapView3D'));

/** Origin id prefix of "plan from the vehicle I am in" (`onboard` in `POST /api/routes`). */
const ONBOARD_PREFIX = 'onboard:';

/** The start "Z pojazdu: 24": the search plans from the vehicle's next stops (`onboard` of `POST /api/routes`). */
const onboardPlace = (v: VehicleCandidate, position: LatLng | null): Place => ({
  id: `${ONBOARD_PREFIX}${v.id}`,
  label: `Z pojazdu: ${v.line} (następne przystanki)`,
  position: position ?? [52.2297, 21.0122],
});

/** The active trip ("Rozpocznij przejazd" ... "Zakończ"): the route being travelled and its ends. */
interface ActiveTrip {
  route: RouteOption;
  origin: Place;
  destination: Place;
  /** Full local departure datetime of the route (today + `route.departure`, or the searched date). */
  startAt: Date;
  /** False while waiting for a later departure: no GPS progress, no off-route check, no recording yet. */
  started: boolean;
}

/** Filter chips that only matter for public transport options. */
const TRANSIT_ONLY_CHIPS: FilterChip['id'][] = ['sort', 'modes', 'walk', 'maxTransfers', 'excludedModes'];

type Step = 'search' | 'options' | 'route';

export default function App() {
  const { mode, toggle } = useColorMode();
  const theme = useTheme();
  // From 600 px: the side panel layout (search + sheets in one column on the left, the map on the right).
  const desktop = useMediaQuery(theme.breakpoints.up('sm'));

  const { position: userPosition, moveHeading, geoError, clearGeoError, locate, getTrack } = useLocationTrack();
  const heading = useHeading(moveHeading);
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  // Intermediate stops (`null` = an empty field the user has just added) and how they are ordered.
  const [stopFields, setStopFields] = useState<(Place | null)[]>([]);
  const [stopOrder, setStopOrder] = useState<StopOrder>('given');
  // Public transport (default) or a street-only trip: walking or own bike.
  const [travel, setTravel] = useState<TravelMode>('transit');
  // The search card on a phone shows only "Dokąd jedziesz?" until it is opened (on a wide screen it is always open).
  const [searchOpen, setSearchOpen] = useState(false);
  // The 3D map prototype (a tilted map with extruded buildings), remembered on the device.
  const [map3d, setMap3d] = useMap3d();
  // Accessibility picked for this search (transit and walking); null = not picked, follow the wheelchair preference.
  const [accessChoice, setAccessChoice] = useState<Access | null>(null);
  // Public transport: reach the stops on foot (default) or by the own bike (then no wheelchair / stroller).
  const [transitAccess, setTransitAccess] = useState<TransitAccess>('walk');
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
  const { record: recordFrequent } = useFrequentPlaces();
  // Filters are sticky for the session (memory only): they stay across new searches and travel-mode switches until
  // the user changes them or taps "Wyczyść filtry". They start from the saved preferences.
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

  // "Which vehicle am I in?" window: detects every 5 s until a vehicle is confirmed and opens as a small bar when it
  // found one (also in the active trip); the bus button on the map / "W jakim pojeździe jestem?" asks at once. In the active trip it
  // detects from the trip's own track (the recorder's points), else from the last 1-3 positions.
  const tripTrack = () => {
    const points = activeTrip ? detectionPoints(tracker.track()) : [];
    return points.length > 0 ? points : getTrack();
  };
  const vehicle = useVehicleDetection({ position: userPosition, geoError, getTrack: tripTrack });
  const progress = useTripProgress(activeTrip?.started ? activeTrip.route : null, userPosition);

  // Waiting for a later departure: a live countdown, then the trip starts by itself (or on "Ruszam teraz").
  const beginRecording = useRef<(() => void) | null>(null);
  const [now, setNow] = useState(() => new Date());
  const waitingTrip = activeTrip !== null && !activeTrip.started;
  useEffect(() => {
    if (!waitingTrip) return;
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, [waitingTrip]);
  const launchTrip = () => {
    beginRecording.current?.();
    beginRecording.current = null;
    setActiveTrip((t) => (t ? { ...t, started: true } : t));
  };
  useEffect(() => {
    if (activeTrip && !activeTrip.started && secondsUntil(activeTrip.startAt, now) <= 0) launchTrip();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTrip, now]);

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
  // A wheelchair in the preferences preselects "Na wózku"; a picked accessibility wins for this search.
  // The own bike as access mode drops the wheelchair / stroller (the backend refuses the pair).
  const byBike = travel === 'transit' && transitAccess === 'bike';
  const access: Access = byBike ? 'standard' : (accessChoice ?? (trip.wheelchair.type !== 'none' ? 'wheelchair' : 'standard'));
  // The vehicle chips of the filters override the preference's excluded modes for this search.
  const search = useMemo(
    () => routeSearchBody(trip, filters.modes, byBike ? 'standard' : accessChoice),
    [trip, filters.modes, accessChoice, byBike],
  );

  const onboardVehicleId = origin?.id.startsWith(ONBOARD_PREFIX) ? origin.id.slice(ONBOARD_PREFIX.length) : null;
  const { options, loading, error: searchError, offline: routesOffline, errorMessage, vehicleNotFound, refresh: refreshRoutes } = useRouteSearch({
    origin,
    destination,
    via,
    order: stopOrder,
    search,
    travel,
    access,
    transitAccess: byBike ? 'bike' : 'walk',
    onboardVehicleId,
    when: departureWhen(departure),
  });

  // The backend does not know the vehicle (404): plan from the GPS position instead, with a short note.
  useEffect(() => {
    if (!vehicleNotFound || !origin?.id.startsWith(ONBOARD_PREFIX)) return;
    setOrigin(currentLocation ?? { id: 'current-location', label: 'Twoja lokalizacja', position: origin.position, isCurrentLocation: true });
    setOnboardNotice(true);
  }, [vehicleNotFound, origin, currentLocation]);

  // A new search starts with no picked / chosen route; the filters stay as they are.
  useEffect(() => {
    setPickedId(null);
    setChosenId(null);
  }, [origin, destination, via, stopOrder, travel, access, byBike, departure]);

  // Every searched trip teaches the frequent places on this device (the search fields suggest them).
  useEffect(() => {
    if (origin && destination) recordFrequent([origin, ...via, destination]);
  }, [origin, destination, via, recordFrequent]);

  // The backend is switched off or could not be reached: say so each time it happens (no made-up data is shown).
  const offlineShown = routesOffline || vehicle.offline;
  const [offlineNoticeOpen, setOfflineNoticeOpen] = useState(false);
  useEffect(() => {
    if (offlineShown) setOfflineNoticeOpen(true);
  }, [offlineShown]);


  // "Wybierz na mapie": the field being picked, and whether the tapped point is being named (nearest stop).
  const [picking, setPicking] = useState<PickTarget | null>(null);
  const [pickBusy, setPickBusy] = useState(false);
  const pickRun = useRef(0);
  const setPlace = (target: PickTarget, place: Place) => {
    if (target === 'origin') setOrigin(place);
    else if (target === 'destination') setDestination(place);
    else setStopFields((prev) => prev.map((s, k) => (k === target ? place : s)));
  };
  const pickAt = async (target: PickTarget, position: LatLng) => {
    const run = ++pickRun.current;
    setPickBusy(true);
    const place = await placeAt(position);
    if (run !== pickRun.current) return; // cancelled meanwhile
    setPickBusy(false);
    setPicking(null);
    setPlace(target, place);
  };
  const cancelPick = () => {
    pickRun.current++;
    setPickBusy(false);
    setPicking(null);
  };
  // Escape leaves the picking too.
  useEffect(() => {
    if (picking === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancelPick();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [picking]);

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
  // Filters that do not apply to a street trip (sorting, vehicles, transfers, max walk) are kept but not shown.
  const chips = useMemo(
    () => filterChips(filters, trip).filter((c) => travel === 'transit' || !TRANSIT_ONLY_CHIPS.includes(c.id)),
    [filters, trip, travel],
  );

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

  const startTrip = (begin: () => void) => {
    if (!chosen || !origin || !destination) return;
    const current = new Date();
    // The route's departure on the searched day (the departure picker's `when`, or today for "now").
    const startAt = tripStartAt(chosen.departure, current, departure);
    const wait = mustWait(startAt, current);
    if (wait) beginRecording.current = begin;
    else begin();
    setNow(current);
    setActiveTrip({ route: chosen, origin, destination, startAt, started: !wait });
    setReplanning(false);
    setTripSnap('middle');
  };

  const endTrip = () => {
    beginRecording.current = null;
    void tracker.stop(); // saves the pace recording, as before (nothing while still waiting)
    setActiveTrip(null);
    setReplanning(false);
    setTripVehicleOpen(false);
    vehicle.forget(); // the trip is over: no "Jedziesz: ..." left behind
  };

  /** "Zmień cel" / "Zmień trasę": the full search card; the start = the confirmed vehicle, else the GPS position. */
  const replan = (keepDestination: boolean) => {
    if (!activeTrip) return;
    const here = userPosition ?? activeTrip.origin.position;
    const v = vehicle.confirmed;
    setOrigin(
      v && !v.manual
        ? onboardPlace(v, here)
        : currentLocation ?? { id: 'current-location', label: 'Twoja lokalizacja', position: here, isCurrentLocation: true },
    );
    setDestination(keepDestination ? activeTrip.destination : null);
    setStopFields([]);
    setTravel('transit');
    setAccessChoice(null);
    setDeparture(null); // a new plan inside a running trip is for now
    setTripVehicleOpen(false);
    setReplanning(true);
  };

  const confirmOption = () => {
    if (activeTrip && replanning) {
      const picked = visible.find((o) => o.id === selectedId);
      if (!picked || !origin || !destination) return;
      // The new route replaces the old one; the trip (and its recording) goes on. Planned from the GPS position
      // (not "Z pojazdu"), it does not continue on the confirmed vehicle: forget it.
      if (!origin.id.startsWith(ONBOARD_PREFIX)) vehicle.forget();
      setActiveTrip({ ...activeTrip, route: picked, origin, destination });
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

  // Parts of the map covered by the panels, so the route stays in the visible area (on a wide screen the map
  // starts right of the side panel, so only small margins).
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

  // The vehicle window ("W jakim pojeździe jesteś?"): in the search step it sits at the bottom; after a route is
  // found the bus button of the map still opens it, in place of the route sheet until it is closed.
  const vehicleWindow = !activeTrip && vehicle.open && picking === null;
  // After a route is found the small bar (found by itself) floats above the route sheet; expanded (or opened with the
  // bus button) the window takes the place of the route sheet until it is collapsed or closed.
  const vehicleOverStep = vehicleWindow && step !== 'search' && vehicle.snap !== 'bar';
  const vehicleAboveSheet = vehicleWindow && step !== 'search' && vehicle.snap === 'bar';
  // Moving on to the routes collapses the window to its bar, so it never hides the route sheet that comes next.
  const collapseVehicle = vehicle.setSnap;
  useEffect(() => {
    if (step !== 'search') collapseVehicle('bar');
  }, [step, collapseVehicle]);

  // Where the round map buttons start: below the search card, whatever its height is.
  const searchCollapsed = !desktop && !searchOpen && !replanning; // a new search during a trip keeps "Wróć do przejazdu" in view
  const mapControlsOffset =
    inTrip || step === 'route'
      ? 0
      : searchCollapsed
        ? -56 + (destination && !origin ? 34 : 0) + 36 + (travel === 'transit' ? 34 : 0) // the folded card shows the mode chips (+ own-bike switch)
        : 84 + stopFields.length * 56 + (hasAccess(travel) && !byBike ? 36 : 0) + (travel === 'transit' ? 36 : 0);

  return (
    <Box sx={{ position: 'fixed', inset: 0, bgcolor: 'background.default' }}>
      {/* Under the Preferences page the map and panels cannot take focus or be read by a screen reader. */}
      <Box
        {...(tab !== 'map' ? ({ inert: '' } as object) : {})}
        sx={tab === 'demo' ? { visibility: 'hidden' } : undefined}
      >
        {/* on a wide screen the map starts right of the side panel, so nothing covers it */}
        <Box sx={{ position: 'absolute', top: 0, right: 0, bottom: 0, left: desktop ? PANEL_WIDTH : 0 }}>
        {map3d && picking === null ? (
          <Suspense fallback={null}>
            <MapView3D
              paletteMode={mode}
              onToggleMode={toggle}
              userPosition={userPosition}
              heading={heading}
              onLocate={locate}
              origin={inTrip ? activeTrip.origin : origin}
              destination={inTrip ? activeTrip.destination : destination}
              route={preview}
              padding={padding}
              stops={inTrip ? [] : via}
              controlsOffset={mapControlsOffset}
              onDetectVehicle={!activeTrip && picking === null ? vehicle.toggle : undefined}
              vehicleOpen={vehicle.open}
              vehicleConfirmed={vehicle.confirmed !== null}
              onClose3d={() => setMap3d(false)}
            />
          </Suspense>
        ) : (
        <MapView
          paletteMode={mode}
          onToggleMode={toggle}
          userPosition={userPosition}
          heading={heading}
          onLocate={locate}
          origin={inTrip ? activeTrip.origin : origin}
          destination={inTrip ? activeTrip.destination : destination}
          route={preview}
          detailed={inTrip || step === 'route'}
          padding={padding}
          stops={inTrip ? [] : via}
          controlsOffset={mapControlsOffset}
          onDetectVehicle={!activeTrip && picking === null ? vehicle.toggle : undefined}
              vehicleOpen={vehicle.open}
              vehicleConfirmed={vehicle.confirmed !== null}
          follow={inTrip}
          focus={
            inTrip && activeTrip.started && progress
              ? { key: `${activeTrip.route.id}:${progress.legIndex}`, path: activeTrip.route.legs[progress.legIndex]?.path ?? [] }
              : null
          }
          onMapPick={picking !== null && !pickBusy ? (p) => void pickAt(picking, p) : undefined}
          onContextPick={!inTrip && picking === null ? (target, p) => void pickAt(target, p) : undefined}
          onOpen3d={() => setMap3d(true)}
          onPlacePick={!inTrip ? (target, place) => { cancelPick(); setPlace(target, place); } : undefined}
        />
        )}
        </Box>

        <SidePanel on={desktop}>

        {picking !== null && <PickBanner target={picking} busy={pickBusy} onCancel={cancelPick} />}

        {!inTrip && step !== 'route' && picking === null && (
          <SearchCard
            collapsed={searchCollapsed}
            onToggleCollapsed={desktop ? undefined : () => setSearchOpen((o) => !o)}
            origin={origin}
            destination={destination}
            stops={stopFields}
            order={stopOrder}
            travel={travel}
            onTravelChange={setTravel}
            access={access}
            onAccessChange={setAccessChoice}
            transitAccess={transitAccess}
            onTransitAccessChange={setTransitAccess}
            departure={departure}
            onDepartureChange={setDeparture}
            currentLocation={currentLocation}
            onOriginChange={setOrigin}
            onDestinationChange={setDestination}
            onStopsChange={setStopFields}
            onOrderChange={setStopOrder}
            onSwap={swap}
            onLocate={handleLocateOrigin}
            onBackToTrip={replanning ? () => setReplanning(false) : undefined}
            onPickOnMap={setPicking}
          />
        )}

        {vehicleWindow && (
          <VehicleSheet
            candidates={vehicle.vehicles}
            lines={vehicle.lines}
            manual={vehicle.manual}
            loading={vehicle.loading}
            offline={vehicle.offline}
            liveUnavailable={vehicle.liveUnavailable}
            snap={vehicle.snap}
            bottomOffset={vehicleAboveSheet ? (step === 'route' ? detailsHeights[detailsSnap] : optionsHeights[optionsSnap]) + 8 : 0}
            selectedId={vehicle.selectedId}
            confirmed={vehicle.confirmed}
            onSnapChange={vehicle.setSnap}
            onSelect={vehicle.setSelectedId}
            onManualLine={vehicle.selectManualLine}
            onClearManual={vehicle.clearManual}
            onRedetect={vehicle.redetect}
            onConfirm={() => {
              // "Jadę tą linią": plan from that vehicle's next stops (unless a start was typed)
              const v = vehicle.confirm();
              if (v && !v.manual && (!origin || origin.isCurrentLocation || origin.id.startsWith(ONBOARD_PREFIX))) {
                setOrigin(onboardPlace(v, userPosition ?? origin?.position ?? null));
              }
              if (step !== 'search') vehicle.hide(); // after a route is found the window must not cover its sheet
            }}
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
            waiting={
              activeTrip.started
                ? null
                : { departure: activeTrip.route.departure, countdown: countdownText(secondsUntil(activeTrip.startAt, now)) }
            }
            onStartNow={launchTrip}
          />
        )}

        {inTrip && vehicle.open && (tripVehicleOpen || !vehicle.confirmed) && (
          <VehicleSheet
            candidates={vehicle.vehicles}
            lines={vehicle.lines}
            manual={vehicle.manual}
            loading={vehicle.loading}
            offline={vehicle.offline}
            liveUnavailable={vehicle.liveUnavailable}
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
              vehicle.hide();
              setTripVehicleOpen(false);
            }}
            onDismiss={() => {
              vehicle.dismiss();
              setTripVehicleOpen(false);
            }}
          />
        )}

        {!inTrip && step === 'options' && picking === null && !vehicleOverStep && (
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
            onConfirm={confirmOption}
            onRefresh={refreshRoutes}
          />
        )}

        {!activeTrip && step === 'route' && chosen && origin && destination && !vehicleOverStep && (
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
        </SidePanel>

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
