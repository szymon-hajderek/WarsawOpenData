import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import { CircleMarker, MapContainer, Marker, Polyline, Popup, useMap, useMapEvents } from 'react-leaflet';
import { Box, Button, type PaletteMode } from '@mui/material';
import { ICON_PATH, MODE_META, iconHtml, modeColor } from '../modes';
import { GLASS, PALETTE } from '../map/palette';
import { MAP_ATTRIBUTION } from '../map/mapStyle';
import { createLookStyle, useMapLook, type MapLook } from '../map/mapLook';
import { useRouteStations } from '../hooks/useRouteStations';
import { useMapOverlays } from '../hooks/useMapOverlays';
import { OVERLAYS } from '../map/overlays';
import { useOverlayIds } from '../hooks/useOverlayIds';
import MapControls from './MapControls';
import { MapOverlays } from './MapOverlays';
import { accessPoints, buildOverlay, type Overlay } from '../utils/overlay';
import { legLines, type LineStyle } from '../utils/legStyle';
import { glassCss } from '../map/glass';
import '../map/glass.css';
import type { LatLng, Place as PlaceT, RouteOption } from '../types';

/** Positions (%) and delays (s) of the twinkling glints on the glass map. */
const GLINTS: [number, number, number][] = [
  [12, 20, 0],
  [78, 14, 1.6],
  [44, 38, 3.1],
  [88, 56, 0.9],
  [22, 66, 2.4],
  [60, 82, 4],
  [8, 88, 1.2],
];

const WARSAW: LatLng = [52.2297, 21.0122];

export interface MapPadding {
  top: number;
  left: number;
  bottom: number;
  right: number;
}

interface Props {
  paletteMode: PaletteMode;
  onToggleMode: () => void;
  userPosition: LatLng | null;
  onLocate: () => void;
  origin: PlaceT | null;
  destination: PlaceT | null;
  /** Route to draw (a preview among options, or the chosen route). */
  route: RouteOption | null;
  /** The chosen route: also draw markers at transfers. */
  detailed: boolean;
  padding: MapPadding;
  /** Intermediate stops as added (numbered markers; the route's own order wins once it is known). */
  stops?: PlaceT[];
  /** Extra top offset (px) of the map buttons on phones, when the search card grows with stops. */
  controlsOffset?: number;
  /** Shows a button that detects the vehicle the user is in (and reopens the vehicle window). */
  onDetectVehicle?: () => void;
  /** The vehicle window is shown: the bus button is pressed and a second click hides it. */
  vehicleOpen?: boolean;
  /** A vehicle is confirmed: a dot on the bus button. */
  vehicleConfirmed?: boolean;
  /** What the phone reports in the demo (with GPS error), drawn as a small dot next to the real position. */
  gpsPosition?: LatLng | null;
  /** Active trip: the map keeps the user's position in view. */
  follow?: boolean;
  /** Active trip: the part of the route being travelled now (zoomed to when it changes). */
  focus?: { key: string; path: LatLng[] } | null;
  /** Picking a point ("Wybierz na mapie"): a tap / click on the map gives its position, the cursor is a crosshair. */
  onMapPick?: (position: LatLng) => void;
  /** Long press / right click on the map offers "Stąd" / "Dotąd" at that point. */
  onContextPick?: (target: 'origin' | 'destination', position: LatLng) => void;
  /** "Stąd" / "Dotąd" in the popup of a stop or Veturilo station of the map overlays. */
  onPlacePick?: (target: 'origin' | 'destination', place: PlaceT) => void;
  /** Opens the 3D map prototype (a button in the map controls). */
  onOpen3d?: () => void;
}

/** Map taps while picking, and the long-press / right-click menu "Stąd" / "Dotąd". */
function MapPicker({ onMapPick, onContextPick }: Pick<Props, 'onMapPick' | 'onContextPick'>) {
  const [menu, setMenu] = useState<LatLng | null>(null);
  useMapEvents({
    click: (e) => onMapPick?.([e.latlng.lat, e.latlng.lng]),
    contextmenu: (e) => {
      if (onContextPick && !onMapPick) setMenu([e.latlng.lat, e.latlng.lng]);
    },
  });
  if (!menu || !onContextPick) return null;
  const pick = (target: 'origin' | 'destination') => {
    setMenu(null);
    onContextPick(target, menu);
  };
  return (
    <Popup position={menu} closeButton={false} eventHandlers={{ remove: () => setMenu(null) }}>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button size="small" variant="outlined" onClick={() => pick('origin')}>
          Stąd
        </Button>
        <Button size="small" variant="contained" onClick={() => pick('destination')}>
          Dotąd
        </Button>
      </Box>
    </Popup>
  );
}

/** Fits the view to what is visible (route / points) and handles the first geolocation fix. */
function MapController({
  origin,
  destination,
  route,
  userPosition,
  padding,
  follow = false,
  focus = null,
}: Pick<Props, 'origin' | 'destination' | 'route' | 'userPosition' | 'padding' | 'follow' | 'focus'>) {
  const map = useMap();
  const centeredOnUser = useRef(false);

  useEffect(() => {
    const points: LatLng[] = route
      ? route.legs.flatMap((l) => l.path)
      : ([origin?.position, destination?.position].filter(Boolean) as LatLng[]);

    if (points.length >= 2) {
      map.flyToBounds(L.latLngBounds(points), {
        paddingTopLeft: [padding.left, padding.top],
        paddingBottomRight: [padding.right, padding.bottom],
        maxZoom: 16,
        duration: 0.8,
      });
    } else if (points.length === 1) {
      map.flyTo(points[0], 15, { duration: 0.8 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, route?.id, origin?.id, destination?.id, padding.top, padding.left, padding.bottom, padding.right]);

  useEffect(() => {
    if (userPosition && !centeredOnUser.current && !origin && !destination) {
      centeredOnUser.current = true;
      map.flyTo(userPosition, 15, { duration: 0.8 });
    }
  }, [map, userPosition, origin, destination]);

  // Active trip: zoom to the leg being travelled (and the user) whenever the current leg changes.
  useEffect(() => {
    if (!focus || focus.path.length === 0) return;
    const pts = userPosition ? [...focus.path, userPosition] : focus.path;
    map.flyToBounds(L.latLngBounds(pts), {
      paddingTopLeft: [padding.left + 24, padding.top + 24],
      paddingBottomRight: [padding.right + 24, padding.bottom + 24],
      maxZoom: 17,
      duration: 0.8,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, focus?.key]);

  useEffect(() => {
    if (follow && userPosition && !map.getBounds().pad(-0.15).contains(userPosition)) map.panTo(userPosition, { animate: true, duration: 0.5 });
  }, [map, follow, userPosition]);

  return null;
}

/** Basemap: flat vector tiles drawn by MapLibre GL inside the Leaflet map. */
function VectorBasemap({ mode, look }: { mode: PaletteMode; look: MapLook }) {
  const map = useMap();
  const layerRef = useRef<L.MaplibreGL | null>(null);
  const styleRef = useRef(createLookStyle(look, mode));

  // One layer for the life of the map (a new one would open a new WebGL context).
  useEffect(() => {
    let cancelled = false;
    // The vector layer does not report its attribution to Leaflet, so add it ourselves.
    map.attributionControl.addAttribution(MAP_ATTRIBUTION);
    // Loaded on demand, so the first paint does not wait for MapLibre.
    import('@maplibre/maplibre-gl-leaflet').then(({ maplibreGL }) => {
      if (cancelled) return;
      layerRef.current = maplibreGL({
        style: styleRef.current,
        attributionControl: false,
      }).addTo(map);
    });
    return () => {
      cancelled = true;
      map.attributionControl.removeAttribution(MAP_ATTRIBUTION);
      layerRef.current?.remove();
      layerRef.current = null;
    };
  }, [map]);

  // Light / dark or look switch: restyle the same layer.
  useEffect(() => {
    styleRef.current = createLookStyle(look, mode);
    layerRef.current?.getMaplibreMap().setStyle(styleRef.current);
  }, [mode, look]);

  // "Breathing" of the glass glow: the glow layers slowly pulse (about 20 frames a second).
  useEffect(() => {
    if (look !== 'glass' || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    let frame = 0;
    let last = 0;
    const tick = (t: number) => {
      frame = requestAnimationFrame(tick);
      if (t - last < 50) return;
      last = t;
      const m = layerRef.current?.getMaplibreMap();
      if (!m || !m.isStyleLoaded()) return;
      const wave = (period: number, phase = 0) => 0.65 + 0.35 * Math.sin((t / period) * Math.PI * 2 + phase);
      const set = (id: string, v: number) => m.getLayer(id) && m.setPaintProperty(id, 'line-opacity', v);
      set('minor-glow', wave(5200));
      set('major-glow', wave(6800, 1.6));
      set('water-shore-glow', wave(4300, 3));
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [look]);

  return null;
}

function RouteLayer({
  route,
  palette,
  detailed,
  look,
  overlay,
}: {
  route: RouteOption;
  palette: PaletteMode;
  detailed: boolean;
  look: MapLook;
  /** Stops of the route (from `GET /api/stations`); `null` until the server has answered or when it has none. */
  overlay: Overlay | null;
}) {
  const colors = PALETTE[palette];
  // Metro platforms are underground: their ride is drawn muted and dashed.
  const underground = !!overlay?.markers.some((m) => m.underground);

  const detailMarkers = useMemo(() => {
    const dot = (size: number, html: string, border: string, opacity = 1) =>
      L.divIcon({
        className: 'app-div-icon',
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        html: `<div style="width:${size}px;height:${size}px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:2px solid ${border};background:${colors.surface};opacity:${opacity}">${html}</div>`,
      });
    const out: { key: string; position: [number, number]; icon: L.DivIcon }[] = [];
    overlay?.markers.forEach((m) => {
      const color = m.station.kind === 'metro_platform' ? MODE_META.metro[palette] : m.station.kind === 'tram_post' ? MODE_META.tram[palette] : m.station.kind === 'veturilo' ? MODE_META.veturilo[palette] : m.station.kind.startsWith('rail') ? MODE_META.rail[palette] : MODE_META.bus[palette];
      out.push({ key: `stop-${m.station.id}`, position: m.station.position, icon: dot(12, '', color, m.underground ? 0.6 : 1) });
    });
    overlay?.entrances.forEach((e, i) => {
      out.push({ key: `entrance-${i}`, position: e, icon: dot(18, iconHtml(ICON_PATH.stairs, 11, MODE_META.metro[palette]), MODE_META.metro[palette]) });
    });
    accessPoints(route).forEach(({ key, kind, position }) =>
      out.push({ key, position, icon: dot(20, iconHtml(kind === 'elevator' ? ICON_PATH.elevator : ICON_PATH.stairs, 13, colors.accent), colors.accent) }),
    );
    return out;
  }, [overlay, route, colors, palette]);

  // Icons are rebuilt only when the route or the colours change, not on every render of the app.
  const transferIcons = useMemo(
    () =>
      detailed
        ? route.legs
            .slice(1)
            .filter((leg) => leg.mode !== 'walk')
            .map((leg) => ({
              position: leg.path[0],
              icon: L.divIcon({
                className: 'app-div-icon',
                iconSize: [26, 26],
                iconAnchor: [13, 13],
                html: `<div style="width:26px;height:26px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;${
                  look === 'glass'
                    ? glassCss(palette)
                    : `border:2px solid ${colors.surface};background:${colors.markerTint};box-shadow:${colors.shadow}`
                }">${iconHtml(
                  MODE_META[leg.mode].path,
                  15,
                  modeColor(leg.mode, palette),
                )}</div>`,
              }),
            }))
        : [],
    [route, detailed, colors, palette, look],
  );

  return (
    <>
      {route.legs.map((leg, i) => {
        const walk = leg.mode === 'walk';
        const color = walk ? colors.accent : modeColor(leg.mode, palette);
        const positions = overlay?.paths[i] ?? leg.path;
        const buried = underground && leg.mode === 'metro';
        // ridden parts solid, pushed parts dashed, steps / elevators / metro access in their own style
        const lines = legLines(leg, positions);
        const options = (style: LineStyle) =>
          style === 'access'
            ? { color: colors.accent, weight: 8, dashArray: '2 6', opacity: 1, lineCap: 'butt' as const }
            : {
                color,
                weight: style === 'dotted' ? 5 : 6,
                dashArray: style === 'dotted' ? '1 10' : style === 'dashed' || buried ? '8 8' : undefined,
                opacity: buried ? 0.55 : 1,
                lineCap: 'round' as const,
              };
        return (
          <Fragment key={`${i}-${leg.mode}`}>
            {!walk && !buried && (
              <Polyline
                positions={positions}
                interactive={false}
                pathOptions={{ color: colors.surface, weight: 12, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }}
              />
            )}
            {lines.map((line, k) => (
              <Polyline
                key={k}
                positions={line.path}
                interactive={false}
                pathOptions={{ ...options(line.style), lineJoin: 'round' }}
              />
            ))}
          </Fragment>
        );
      })}

      {transferIcons.map(({ position, icon }, i) => (
        <Marker key={`transfer-${i}`} position={position} interactive={false} icon={icon} />
      ))}

      {detailMarkers.map(({ key, position, icon }) => (
        <Marker key={key} position={position} interactive={false} icon={icon} />
      ))}
    </>
  );
}

/** Numbered round marker of an intermediate stop. */
function stopIcon(n: number, colors: (typeof PALETTE)['light'], look: MapLook, mode: PaletteMode): L.DivIcon {
  const fill =
    look === 'glass'
      ? glassCss(mode, mode === 'dark' ? 'rgba(255, 199, 44, 0.78)' : 'rgba(200, 16, 46, 0.82)')
      : `border:3px solid ${colors.surface};background:${colors.accent};box-shadow:${colors.shadow}`;
  return L.divIcon({
    className: 'app-div-icon',
    html: `<div style="width:24px;height:24px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;${fill};color:${colors.theme.primary.contrastText};font:700 12px/1 Roboto,sans-serif">${n}</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

export default function MapView({
  paletteMode,
  onToggleMode,
  userPosition,
  onLocate,
  origin,
  destination,
  route,
  detailed,
  padding,
  stops = [],
  controlsOffset = 0,
  onDetectVehicle,
  vehicleOpen = false,
  vehicleConfirmed = false,
  gpsPosition = null,
  follow = false,
  onMapPick,
  onContextPick,
  onPlacePick,
  onOpen3d,
  focus = null,
}: Props) {
  const [map, setMap] = useState<L.Map | null>(null);
  const [overlayIds, toggleOverlay] = useOverlayIds();
  const overlayData = useMapOverlays(map, overlayIds);
  const colors = PALETTE[paletteMode];
  const [look] = useMapLook();
  const stations = useRouteStations(route);
  const overlay = useMemo(() => (route && stations.size > 0 ? buildOverlay(route, stations) : null), [route, stations]);
  const glass = look === 'glass';
  const g = GLASS[paletteMode];

  const icons = useMemo(() => {
    const { accent, surface, shadow } = colors;
    const gl = (tint?: string) => glassCss(paletteMode, tint);
    if (glass) {
      const red = paletteMode === 'dark' ? 'rgba(255, 199, 44, 0.8)' : 'rgba(200, 16, 46, 0.85)';
      return {
        user: L.divIcon({
          className: 'app-div-icon',
          html: `<div class="glass-pulse glass-rim" style="--pulse-color:${accent};position:relative;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;${gl()}">${iconHtml(
            ICON_PATH.navigation,
            18,
            accent,
          )}</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        }),
        origin: L.divIcon({
          className: 'app-div-icon',
          html: `<div style="width:22px;height:22px;box-sizing:border-box;border-radius:50%;${gl()};outline:4px solid ${accent};outline-offset:-5px"></div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        }),
        destination: L.divIcon({
          className: 'app-div-icon',
          html: `<div class="glass-pulse glass-rim" style="--pulse-color:${accent};position:relative;width:32px;height:32px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;${gl(red)}">${iconHtml(
            ICON_PATH.place,
            18,
            colors.theme.primary.contrastText,
          )}</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        }),
      };
    }
    return {
      // white circle with a navigation arrow
      user: L.divIcon({
        className: 'app-div-icon',
        html: `<div style="width:32px;height:32px;border-radius:50%;display:grid;place-items:center;background:${surface};box-shadow:${shadow}">${iconHtml(
          ICON_PATH.navigation,
          18,
          accent,
        )}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      }),
      origin: L.divIcon({
        className: 'app-div-icon',
        html: `<div style="width:20px;height:20px;box-sizing:border-box;border-radius:50%;border:5px solid ${accent};background:${surface};box-shadow:${shadow}"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      }),
      // round accent circle with a white pin
      destination: L.divIcon({
        className: 'app-div-icon',
        html: `<div style="width:32px;height:32px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:2px solid ${surface};background:${accent};box-shadow:${shadow}">${iconHtml(
          ICON_PATH.place,
          18,
          colors.theme.primary.contrastText,
        )}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      }),
    };
  }, [colors, glass, paletteMode]);

  return (
    <>
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          ...(onMapPick && { '& .leaflet-container, & .leaflet-container.leaflet-grab': { cursor: 'crosshair' } }),
        }}
      >
        <MapContainer
          ref={setMap}
          center={WARSAW}
          zoom={13}
          maxZoom={19}
          zoomControl={false}
          style={{ height: '100%', width: '100%' }}
        >
          <VectorBasemap mode={paletteMode} look={look} />
          <MapPicker onMapPick={onMapPick} onContextPick={onContextPick} />
          <MapController
            origin={origin}
            destination={destination}
            route={route}
            userPosition={userPosition}
            padding={padding}
            follow={follow}
            focus={focus}
          />
          <MapOverlays
            stations={overlayData.stations}
            status={overlayData.status}
            paletteMode={paletteMode}
            onPlacePick={onPlacePick}
          />
          {route && <RouteLayer route={route} palette={paletteMode} detailed={detailed} look={look} overlay={overlay} />}
          {gpsPosition && (
            <CircleMarker
              center={gpsPosition}
              radius={5}
              pathOptions={{ color: colors.routeEnd, fillColor: colors.routeEnd, fillOpacity: 0.9, weight: 1 }}
              interactive={false}
            />
          )}
          {userPosition && <Marker position={userPosition} icon={icons.user} interactive={false} />}
          {origin && !origin.isCurrentLocation && (
            <Marker position={origin.position} icon={icons.origin} interactive={false} />
          )}
          {destination && <Marker position={destination.position} icon={icons.destination} interactive={false} />}
          {(route?.waypoints?.length ? route.waypoints.slice(1, -1) : stops).map((p, i) => (
            <Marker key={`${p.id}-${i}`} position={p.position} icon={stopIcon(i + 1, colors, look, paletteMode)} interactive={false} />
          ))}
        </MapContainer>
        {glass && (
          <div
            className="glass-sheen"
            aria-hidden
            style={
              {
                '--sheen-yellow': g.sheenYellow,
                '--sheen-red': g.sheenRed,
                '--sheen-band': g.sheenBand,
              } as React.CSSProperties
            }
          >
            <i />
            {GLINTS.map(([x, y, delay], n) => (
              <span key={n} className="glass-glint" style={{ left: `${x}%`, top: `${y}%`, animationDelay: `${delay}s` }} />
            ))}
          </div>
        )}
      </Box>

      {/* map controls: the same buttons as on the 3D map */}
      <MapControls
        paletteMode={paletteMode}
        onToggleMode={onToggleMode}
        view3d={false}
        onSwitchView={() => onOpen3d?.()}
        overlayIds={overlayIds}
        onToggleOverlay={toggleOverlay}
        overlayZoomedOut={OVERLAYS.some((o) => overlayIds.includes(o.id) && overlayData.zoom < o.minZoom)}
        onLocate={onLocate}
        onDetectVehicle={onDetectVehicle}
        vehicleOpen={vehicleOpen}
        vehicleConfirmed={vehicleConfirmed}
        controlsOffset={controlsOffset}
      />
    </>
  );
}
