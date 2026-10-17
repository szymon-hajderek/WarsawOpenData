import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import L from 'leaflet';
import { CircleMarker, MapContainer, Marker, Polyline, useMap } from 'react-leaflet';
import { Box, IconButton, type PaletteMode } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Remove from '@mui/icons-material/Remove';
import MyLocation from '@mui/icons-material/MyLocation';
import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import DirectionsBus from '@mui/icons-material/DirectionsBus';
import Layers from '@mui/icons-material/Layers';
import { ICON_PATH, MODE_META, iconHtml, modeColor } from '../modes';
import { GLASS, PALETTE } from '../map/palette';
import { MAP_ATTRIBUTION } from '../map/mapStyle';
import { createLookStyle, useMapLook, type MapLook } from '../map/mapLook';
import { glassCss, glassStyle } from '../map/glass';
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
  /** What the phone reports in the demo (with GPS error), drawn as a small dot next to the real position. */
  gpsPosition?: LatLng | null;
}

/** Fits the view to what is visible (route / points) and handles the first geolocation fix. */
function MapController({
  origin,
  destination,
  route,
  userPosition,
  padding,
}: Pick<Props, 'origin' | 'destination' | 'route' | 'userPosition' | 'padding'>) {
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
}: {
  route: RouteOption;
  palette: PaletteMode;
  detailed: boolean;
  look: MapLook;
}) {
  const colors = PALETTE[palette];

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
                iconSize: [38, 38],
                iconAnchor: [19, 19],
                html: `<div style="width:38px;height:38px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;${
                  look === 'glass'
                    ? glassCss(palette)
                    : `border:3px solid ${colors.surface};background:${colors.markerTint};box-shadow:${colors.shadow}`
                }">${iconHtml(
                  MODE_META[leg.mode].path,
                  20,
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
        return (
          <Fragment key={`${i}-${leg.mode}`}>
            {!walk && (
              <Polyline
                positions={leg.path}
                interactive={false}
                pathOptions={{ color: colors.surface, weight: 12, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }}
              />
            )}
            <Polyline
              positions={leg.path}
              interactive={false}
              pathOptions={{
                color,
                weight: walk ? 5 : 6,
                dashArray: walk ? '1 10' : undefined,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
          </Fragment>
        );
      })}

      {transferIcons.map(({ position, icon }, i) => (
        <Marker key={`transfer-${i}`} position={position} interactive={false} icon={icon} />
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
    html: `<div style="width:30px;height:30px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;${fill};color:${colors.theme.primary.contrastText};font:700 13px/1 Roboto,sans-serif">${n}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
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
  gpsPosition = null,
}: Props) {
  const [map, setMap] = useState<L.Map | null>(null);
  const colors = PALETTE[paletteMode];
  const [look, toggleLook] = useMapLook();
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
          html: `<div class="glass-pulse glass-rim" style="--pulse-color:${accent};position:relative;width:42px;height:42px;border-radius:50%;display:grid;place-items:center;${gl()}">${iconHtml(
            ICON_PATH.navigation,
            24,
            accent,
          )}</div>`,
          iconSize: [42, 42],
          iconAnchor: [21, 21],
        }),
        origin: L.divIcon({
          className: 'app-div-icon',
          html: `<div style="width:22px;height:22px;box-sizing:border-box;border-radius:50%;${gl()};outline:4px solid ${accent};outline-offset:-5px"></div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        }),
        destination: L.divIcon({
          className: 'app-div-icon',
          html: `<div class="glass-pulse glass-rim" style="--pulse-color:${accent};position:relative;width:44px;height:44px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;${gl(red)}">${iconHtml(
            ICON_PATH.place,
            24,
            colors.theme.primary.contrastText,
          )}</div>`,
          iconSize: [44, 44],
          iconAnchor: [22, 22],
        }),
      };
    }
    return {
      // white circle with a navigation arrow
      user: L.divIcon({
        className: 'app-div-icon',
        html: `<div style="width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:${surface};box-shadow:${shadow}">${iconHtml(
          ICON_PATH.navigation,
          24,
          accent,
        )}</div>`,
        iconSize: [42, 42],
        iconAnchor: [21, 21],
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
        html: `<div style="width:44px;height:44px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:3px solid ${surface};background:${accent};box-shadow:${shadow}">${iconHtml(
          ICON_PATH.place,
          24,
          colors.theme.primary.contrastText,
        )}</div>`,
        iconSize: [44, 44],
        iconAnchor: [22, 22],
      }),
    };
  }, [colors, glass, paletteMode]);

  // Round floating button
  const fab = (child: ReactNode) => (
    <Box
      className={glass ? 'glass-rim' : undefined}
      sx={{
        borderRadius: '50%',
        ...(glass ? glassStyle(paletteMode) : { bgcolor: colors.surface, boxShadow: colors.shadow }),
        '& .MuiIconButton-root': { width: 46, height: 46, color: colors.accent },
      }}
    >
      {child}
    </Box>
  );

  return (
    <>
      <Box sx={{ position: 'absolute', inset: 0 }}>
        <MapContainer
          ref={setMap}
          center={WARSAW}
          zoom={13}
          maxZoom={19}
          zoomControl={false}
          style={{ height: '100%', width: '100%' }}
        >
          <VectorBasemap mode={paletteMode} look={look} />
          <MapController
            origin={origin}
            destination={destination}
            route={route}
            userPosition={userPosition}
            padding={padding}
          />
          {route && <RouteLayer route={route} palette={paletteMode} detailed={detailed} look={look} />}
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

      {/* map controls: theme, location, zoom */}
      <Box
        sx={{
          position: 'absolute',
          zIndex: 900,
          right: { xs: 12, sm: 16 },
          top: { xs: `calc(env(safe-area-inset-top) + ${156 + controlsOffset}px)`, sm: 'calc(env(safe-area-inset-top) + 16px)' },
          display: 'flex',
          flexDirection: 'column',
          gap: 1.25,
        }}
      >
        {fab(
          <IconButton
            aria-label={paletteMode === 'dark' ? 'Włącz jasny motyw' : 'Włącz ciemny motyw'}
            onClick={onToggleMode}
          >
            {paletteMode === 'dark' ? <LightMode /> : <DarkMode />}
          </IconButton>,
        )}
        {fab(
          <IconButton
            aria-label={glass ? 'Włącz płaską wersję mapy' : 'Włącz szklaną wersję mapy'}
            aria-pressed={glass}
            onClick={toggleLook}
          >
            <Layers />
          </IconButton>,
        )}
        {onDetectVehicle &&
          fab(
            <IconButton aria-label="Wykryj pojazd, w którym jesteś" onClick={onDetectVehicle}>
              <DirectionsBus />
            </IconButton>,
          )}
        {fab(
          <IconButton aria-label="Moja lokalizacja" onClick={onLocate}>
            <MyLocation />
          </IconButton>,
        )}
        {fab(
          <IconButton aria-label="Przybliż" onClick={() => map?.zoomIn()}>
            <Add />
          </IconButton>,
        )}
        {fab(
          <IconButton aria-label="Oddal" onClick={() => map?.zoomOut()}>
            <Remove />
          </IconButton>,
        )}
      </Box>
    </>
  );
}
