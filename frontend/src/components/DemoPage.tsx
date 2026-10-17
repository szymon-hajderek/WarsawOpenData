import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  MenuItem,
  Paper,
  Slider,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import type { PaletteMode } from "@mui/material";
import PlayArrow from "@mui/icons-material/PlayArrow";
import Pause from "@mui/icons-material/Pause";
import MapView, { type MapPadding } from "./MapView";
import SearchCard from "./SearchCard";
import VehicleSheet from "./VehicleSheet";
import type { SheetSnap } from "./SnapSheet";
import { fetchRouteOptions } from "../api/routes";
import {
  loadScenario,
  simRide,
  simScenarios,
  simState,
  type SimScenario,
  type SimState,
} from "../api/sim";
import { useRidePlayback, type Speed } from "../hooks/useRidePlayback";
import type { Ride } from "../sim/ride";
import { MODE_META } from "../modes";
import { BOTTOM_NAV_HEIGHT, RADIUS } from "../layout";
import type { Place, RouteOption, VehicleCandidate } from "../types";

const FREE = "free";
const NOISES = [10, 30, 50];
const PADDING: MapPadding = {
  top: 150,
  left: 40,
  bottom: BOTTOM_NAV_HEIGHT + 260,
  right: 40,
};

const mmss = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/**
 * Demo tab (only when the backend runs in simulation mode): pick a scenario or any route, pick an option,
 * and watch a simulated user travel it. The backend computes the whole ride (`POST /api/sim/ride`),
 * this page plays it back: pause, speed, time slider, and the vehicle detection window.
 */
export default function DemoPage({
  paletteMode,
  onToggleMode,
}: {
  paletteMode: PaletteMode;
  onToggleMode: () => void;
}) {
  const [scenarios, setScenarios] = useState<SimScenario[]>([]);
  const [sim, setSim] = useState<SimState | null>(null);
  const [scenario, setScenario] = useState<string>(FREE);
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [hour, setHour] = useState("08:00");
  const [noise, setNoise] = useState(30);
  const [options, setOptions] = useState<RouteOption[]>([]);
  const [searching, setSearching] = useState(false);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [computing, setComputing] = useState(false);
  const [error, setError] = useState("");
  const [ride, setRide] = useState<Ride | null>(null);
  const [rideOption, setRideOption] = useState<RouteOption | null>(null);
  const [vehicleSnap, setVehicleSnap] = useState<SheetSnap>("middle");
  const player = useRidePlayback(ride);

  useEffect(() => {
    void simScenarios()
      .then((all) => setScenarios(all.filter((s) => s.trip)))
      .catch(() => setError("Nie udało się pobrać scenariuszy."));
    void simState().then(setSim);
  }, []);

  const date = sim?.time.slice(0, 10) ?? "";

  const pick = async (name: string) => {
    setScenario(name);
    setRide(null);
    setPickedId(null);
    setError("");
    if (name === FREE) {
      setOrigin(null);
      setDestination(null);
      setHour("08:00");
      return;
    }
    try {
      const state = await loadScenario(name);
      setSim(state);
      setHour(state.time.slice(11, 16));
      const trip = scenarios.find((s) => s.name === name)?.trip;
      if (trip) {
        setOrigin(trip.from);
        setDestination(trip.to);
      }
    } catch {
      setError("Nie udało się wczytać scenariusza.");
    }
  };

  // The route list for the chosen points; the simulated date and hour go in `when` (the engine reads the real clock).
  useEffect(() => {
    setOptions([]);
    setPickedId(null);
    if (!origin || !destination || !date) return;
    const ac = new AbortController();
    setSearching(true);
    setError("");
    fetchRouteOptions(
      {
        from: origin,
        to: destination,
        profile: "standard",
        when: `${date}T${hour}:00`,
      },
      ac.signal,
    )
      .then((r) => {
        setOptions(r.options);
        setSearching(false);
        if (r.mock)
          setError(
            "Serwer nie odpowiedział. To są dane przykładowe, nie da się ich symulować.",
          );
        else if (r.options.length === 0)
          setError("Brak opcji dla tej trasy i godziny.");
      })
      .catch(() => {
        if (!ac.signal.aborted) {
          setSearching(false);
          setError("Nie udało się pobrać tras.");
        }
      });
    return () => ac.abort();
  }, [origin, destination, hour, date]);

  const start = async () => {
    const option = options.find((o) => o.id === pickedId);
    if (!option) return;
    setComputing(true);
    setError("");
    try {
      const r = await simRide(option, "standard", noise);
      setRide(r);
      setRideOption(option);
      if (!r.ok) setError(`Przejazd nie doszedł do celu: ${r.reason}`);
    } catch {
      setError("Nie udało się policzyć przejazdu.");
    } finally {
      setComputing(false);
    }
  };

  const sample = player.sample;
  const candidates = useMemo<VehicleCandidate[]>(
    () =>
      (sample?.detection?.candidates ?? []).map((c) => ({
        id: c.id,
        mode: c.mode,
        line: c.line,
        direction: c.direction,
        vehicleNo: c.vehicle,
        brigade: c.brigade,
        distanceM: c.rmse_m,
      })),
    [sample?.detection],
  );

  const previewRoute = ride
    ? rideOption
    : (options.find((o) => o.id === pickedId) ?? null);
  const leg = ride && sample ? ride.plan[sample.leg] : null;
  const status = !sample
    ? ""
    : sample.event?.event === "board" && sample.vehicle
      ? `Jedzie ${sample.event.line} (${sample.vehicle})`
      : leg
        ? `Odcinek ${sample.leg + 1}/${ride?.plan.length}: ${MODE_META[leg.mode as keyof typeof MODE_META]?.label ?? leg.mode}${leg.line ? ` ${leg.line}` : ""}`
        : "";

  return (
    <Box
      sx={{
        position: "absolute",
        inset: 0,
        zIndex: 1100,
        bgcolor: "background.default",
      }}
    >
      <MapView
        paletteMode={paletteMode}
        onToggleMode={onToggleMode}
        userPosition={sample?.truth ?? null}
        gpsPosition={sample?.gps ?? null}
        onLocate={() => undefined}
        origin={origin}
        destination={destination}
        route={previewRoute}
        detailed
        padding={PADDING}
      />

      {scenario === FREE && !ride && (
        <SearchCard
          origin={origin}
          destination={destination}
          stops={[]}
          order="given"
          currentLocation={null}
          onOriginChange={setOrigin}
          onDestinationChange={setDestination}
          onStopsChange={() => undefined}
          onOrderChange={() => undefined}
          onSwap={() => {
            setOrigin(destination);
            setDestination(origin);
          }}
          onLocate={() => undefined}
        />
      )}

      <Paper
        elevation={6}
        sx={{
          position: "fixed",
          zIndex: 1150,
          left: 12,
          right: 12,
          maxWidth: 440,
          top:
            scenario === FREE && !ride
              ? 190
              : "calc(env(safe-area-inset-top) + 12px)",
          maxHeight: `calc(100% - ${BOTTOM_NAV_HEIGHT + 260}px)`,
          overflowY: "auto",
          p: 1.5,
          borderRadius: RADIUS.card,
          display: "flex",
          flexDirection: "column",
          gap: 1.25,
        }}
      >
        <Box sx={{ display: "flex", gap: 1 }}>
          <TextField
            select
            size="small"
            label="Przejazd"
            value={scenario}
            onChange={(e) => void pick(e.target.value)}
            disabled={computing}
            sx={{ flex: 1, minWidth: 0 }}
            inputProps={{ id: "demo-scenario" }}
          >
            <MenuItem value={FREE}>Dowolna trasa</MenuItem>
            {scenarios.map((s) => (
              <MenuItem key={s.name} value={s.name}>
                {s.title}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            type="time"
            label="Godzina"
            value={hour}
            onChange={(e) => setHour(e.target.value)}
            disabled={computing || !!ride}
            sx={{ width: 110 }}
            inputProps={{ id: "demo-hour" }}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Box>

        {error && <Alert severity="warning">{error}</Alert>}

        {!ride && (
          <>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Błąd GPS
              </Typography>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={noise}
                onChange={(_, v: number | null) => v && setNoise(v)}
                aria-label="Błąd GPS w metrach"
              >
                {NOISES.map((n) => (
                  <ToggleButton key={n} value={n} sx={{ px: 1.25, py: 0.25 }}>
                    {n} m
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>

            {searching && (
              <CircularProgress size={22} aria-label="Szukam tras" />
            )}
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 1,
                maxHeight: 220,
                overflowY: "auto",
              }}
            >
              {options.map((o) => (
                <Box
                  key={o.id}
                  component="button"
                  type="button"
                  onClick={() => setPickedId(o.id)}
                  aria-pressed={o.id === pickedId}
                  sx={(t) => ({
                    textAlign: "left",
                    cursor: "pointer",
                    font: "inherit",
                    color: "text.primary",
                    bgcolor: "background.paper",
                    p: 1.25,
                    borderRadius: RADIUS.tile,
                    border: `2px solid ${o.id === pickedId ? t.palette.primary.main : t.palette.divider}`,
                  })}
                >
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {o.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {o.departure}–{o.arrival} · {o.durationMin} min ·
                    przesiadki: {o.transfers}
                  </Typography>
                </Box>
              ))}
            </Box>
            <Button
              variant="contained"
              disabled={!pickedId || computing}
              onClick={() => void start()}
            >
              {computing ? "Liczę przejazd (do minuty)…" : "Symuluj przejazd"}
            </Button>
            {computing && (
              <CircularProgress size={22} aria-label="Liczę przejazd" />
            )}
          </>
        )}

        {ride && (
          <>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <IconButton
                color="primary"
                onClick={player.toggle}
                aria-label={player.playing ? "Pauza" : "Start"}
                disabled={ride.fixes.length === 0}
              >
                {player.playing ? <Pause /> : <PlayArrow />}
              </IconButton>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={player.speed}
                onChange={(_, v: Speed | null) => v && player.setSpeed(v)}
                aria-label="Szybkość odtwarzania"
              >
                {[1, 10, 60].map((s) => (
                  <ToggleButton key={s} value={s} sx={{ px: 1.25, py: 0.25 }}>
                    {s}x
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
              <Typography
                variant="body2"
                sx={{ ml: "auto", fontVariantNumeric: "tabular-nums" }}
              >
                {mmss(player.elapsed)} / {mmss(player.duration)}
              </Typography>
            </Box>
            <Slider
              size="small"
              min={0}
              max={Math.max(1, player.duration)}
              value={player.elapsed}
              onChange={(_, v) => player.seek(v as number)}
              aria-label="Czas przejazdu"
            />
            <Typography variant="body2" color="text.secondary">
              {status}
            </Typography>
            <Button size="small" onClick={() => setRide(null)}>
              Wybierz inny przejazd
            </Button>
          </>
        )}
      </Paper>

      {ride && candidates.length > 0 && (
        <VehicleSheet
          candidates={candidates}
          lines={[]}
          manual={null}
          loading={false}
          mock={false}
          snap={vehicleSnap}
          selectedId={candidates[0].id}
          confirmed={null}
          onSnapChange={setVehicleSnap}
          onSelect={() => undefined}
          onManualLine={() => undefined}
          onClearManual={() => undefined}
          onRedetect={() => undefined}
          onConfirm={() => undefined}
          onDismiss={() => undefined}
        />
      )}
    </Box>
  );
}
