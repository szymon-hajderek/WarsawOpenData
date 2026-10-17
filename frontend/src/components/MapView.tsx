import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, Polyline, useMap } from 'react-leaflet';
import { Box, IconButton, type PaletteMode } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Remove from '@mui/icons-material/Remove';
import MyLocation from '@mui/icons-material/MyLocation';
import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import Place from '@mui/icons-material/Place';
import Layers from '@mui/icons-material/Layers';
import Navigation from '@mui/icons-material/Navigation';
import { MODE_META, iconHtml, modeColor } from '../modes';
import { useMapLook } from '../mapLook';
import { LOOKS, type MapLook } from '../map/looks';
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
function VectorBasemap({ look, mode }: { look: MapLook; mode: PaletteMode }) {
  const map = useMap();

  useEffect(() => {
    let layer: L.MaplibreGL | undefined;
    let cancelled = false;
    // The vector layer does not report its attribution to Leaflet, so add it ourselves.
    map.attributionControl.addAttribution(MAP_ATTRIBUTION);
    // Loaded on demand, so the first paint does not wait for MapLibre.
    import('@maplibre/maplibre-gl-leaflet').then(({ maplibreGL }) => {
      if (cancelled) return;
      layer = maplibreGL({
        style: createStyle(look, mode),
        attributionControl: false,
      }).addTo(map);
    });
    return () => {
      cancelled = true;
      map.attributionControl.removeAttribution(MAP_ATTRIBUTION);
      layer?.remove();
    };
  }, [map, look, mode]);

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
  const colors = LOOKS[look][palette];

  return (
    <>
      {route.legs.map((leg, i) => {
        const walk = leg.mode === 'walk';
        const color = walk ? colors.accent : modeColor(leg.mode, palette);
        return (
          <Fragment key={i}>
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

      {detailed &&
        route.legs
          .slice(1)
          .filter((leg) => leg.mode !== 'walk')
          .map((leg, i) => (
            <Marker
              key={i}
              position={leg.path[0]}
              interactive={false}
              icon={L.divIcon({
                className: 'app-div-icon',
                iconSize: [38, 38],
                iconAnchor: [19, 19],
                html: `<div style="width:38px;height:38px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:3px solid ${
                  colors.surface
                };background:${colors.markerTint};box-shadow:${colors.shadow}">${iconHtml(
                  MODE_META[leg.mode].icon,
                  20,
                  modeColor(leg.mode, palette),
                )}</div>`,
              })}
            />
          ))}
    </>
  );
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
}: Props) {
  const { look, toggle: toggleLook } = useMapLook();
  const [map, setMap] = useState<L.Map | null>(null);
  const colors = LOOKS[look][paletteMode];

  const icons = useMemo(() => {
    const { accent, surface, shadow } = colors;
    return {
      // white circle with a navigation arrow
      user: L.divIcon({
        className: 'app-div-icon',
        html: `<div style="width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:${surface};box-shadow:${shadow}">${iconHtml(
          Navigation,
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
          Place,
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
          <VectorBasemap look={look} mode={paletteMode} />
          <MapController
            origin={origin}
            destination={destination}
            route={route}
            userPosition={userPosition}
            padding={padding}
          />
          {route && <RouteLayer route={route} palette={paletteMode} detailed={detailed} look={look} />}
          {userPosition && <Marker position={userPosition} icon={icons.user} interactive={false} />}
          {origin && !origin.isCurrentLocation && (
            <Marker position={origin.position} icon={icons.origin} interactive={false} />
          )}
          {destination && <Marker position={destination.position} icon={icons.destination} interactive={false} />}
        </MapContainer>
      </Box>

      {/* map controls: map look, theme, location, zoom */}
      <Box
        sx={{
          position: 'absolute',
          zIndex: 900,
          right: { xs: 12, sm: 16 },
          top: { xs: 'calc(env(safe-area-inset-top) + 156px)', sm: 'calc(env(safe-area-inset-top) + 16px)' },
          display: 'flex',
          flexDirection: 'column',
          gap: 1.25,
        }}
      >
        {fab(
          <IconButton aria-label="Zmień styl mapy" onClick={toggleLook}>
            <Layers />
          </IconButton>,
        )}
        {fab(
          <IconButton
            aria-label={paletteMode === 'dark' ? 'Włącz jasny motyw' : 'Włącz ciemny motyw'}
            onClick={onToggleMode}
          >
            {paletteMode === 'dark' ? <LightMode /> : <DarkMode />}
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
