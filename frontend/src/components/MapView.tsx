import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, Polyline, useMap } from 'react-leaflet';
import { Box, IconButton, type PaletteMode } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Remove from '@mui/icons-material/Remove';
import MyLocation from '@mui/icons-material/MyLocation';
import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import DirectionsBus from '@mui/icons-material/DirectionsBus';
import { ICON_PATH, MODE_META, iconHtml, modeColor } from '../modes';
import { PALETTE } from '../map/palette';
import { createStyle, MAP_ATTRIBUTION } from '../map/mapStyle';
import type { LatLng, Place as PlaceT, RouteOption } from '../types';

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
function VectorBasemap({ mode }: { mode: PaletteMode }) {
  const map = useMap();
  const layerRef = useRef<L.MaplibreGL | null>(null);
  const modeRef = useRef(mode);

  // One layer for the life of the map (a new one would open a new WebGL context).
  useEffect(() => {
    let cancelled = false;
    // The vector layer does not report its attribution to Leaflet, so add it ourselves.
    map.attributionControl.addAttribution(MAP_ATTRIBUTION);
    // Loaded on demand, so the first paint does not wait for MapLibre.
    import('@maplibre/maplibre-gl-leaflet').then(({ maplibreGL }) => {
      if (cancelled) return;
      layerRef.current = maplibreGL({
        style: createStyle(modeRef.current),
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

  // Light / dark switch: restyle the same layer.
  useEffect(() => {
    modeRef.current = mode;
    layerRef.current?.getMaplibreMap().setStyle(createStyle(mode));
  }, [mode]);

  return null;
}

function RouteLayer({
  route,
  palette,
  detailed,
}: {
  route: RouteOption;
  palette: PaletteMode;
  detailed: boolean;
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
                html: `<div style="width:38px;height:38px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:3px solid ${
                  colors.surface
                };background:${colors.markerTint};box-shadow:${colors.shadow}">${iconHtml(
                  MODE_META[leg.mode].path,
                  20,
                  modeColor(leg.mode, palette),
                )}</div>`,
              }),
            }))
        : [],
    [route, detailed, colors, palette],
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
function stopIcon(n: number, colors: (typeof PALETTE)['light']): L.DivIcon {
  return L.divIcon({
    className: 'app-div-icon',
    html: `<div style="width:30px;height:30px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:3px solid ${colors.surface};background:${colors.accent};color:${colors.theme.primary.contrastText};font:700 13px/1 Roboto,sans-serif;box-shadow:${colors.shadow}">${n}</div>`,
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
}: Props) {
  const [map, setMap] = useState<L.Map | null>(null);
  const colors = PALETTE[paletteMode];

  const icons = useMemo(() => {
    const { accent, surface, shadow } = colors;
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
  }, [colors]);

  // Round floating button
  const fab = (child: ReactNode) => (
    <Box
      sx={{
        borderRadius: '50%',
        bgcolor: colors.surface,
        boxShadow: colors.shadow,
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
          <VectorBasemap mode={paletteMode} />
          <MapController
            origin={origin}
            destination={destination}
            route={route}
            userPosition={userPosition}
            padding={padding}
          />
          {route && <RouteLayer route={route} palette={paletteMode} detailed={detailed} />}
          {userPosition && <Marker position={userPosition} icon={icons.user} interactive={false} />}
          {origin && !origin.isCurrentLocation && (
            <Marker position={origin.position} icon={icons.origin} interactive={false} />
          )}
          {destination && <Marker position={destination.position} icon={icons.destination} interactive={false} />}
          {(route?.waypoints?.length ? route.waypoints.slice(1, -1) : stops).map((p, i) => (
            <Marker key={`${p.id}-${i}`} position={p.position} icon={stopIcon(i + 1, colors)} interactive={false} />
          ))}
        </MapContainer>
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
