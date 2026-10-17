import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, Polyline, TileLayer, useMap } from 'react-leaflet';
import { Box, IconButton, Paper, useTheme, type PaletteMode } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Remove from '@mui/icons-material/Remove';
import MyLocation from '@mui/icons-material/MyLocation';
import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import Place from '@mui/icons-material/Place';
import { MODE_META, iconHtml, modeColor } from '../modes';
import type { LatLng, Place as PlaceT, RouteOption } from '../types';

const WARSAW: LatLng = [52.2297, 21.0122];

// Standard OpenStreetMap tiles (no API key). Dark mode is a CSS filter (see index.css).
// For production use a tile provider / self-hosted tiles, per the OSM tile usage policy.
const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

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

function RouteLayer({
  route,
  palette,
  detailed,
}: {
  route: RouteOption;
  palette: PaletteMode;
  detailed: boolean;
}) {
  const casing = palette === 'dark' ? '#0E1116' : '#FFFFFF';

  return (
    <>
      {route.legs.map((leg, i) => {
        const color = modeColor(leg.mode, palette);
        const walk = leg.mode === 'walk';
        return (
          <Fragment key={i}>
            {!walk && (
              <Polyline
                positions={leg.path}
                interactive={false}
                pathOptions={{ color: casing, weight: 10, opacity: 0.9, lineCap: 'round', lineJoin: 'round' }}
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
                className: palette === 'dark' ? 'route-glow' : undefined,
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
              iconSize: [34, 34],
              iconAnchor: [17, 17],
              html: `<div class="stop-marker" style="border-color:${modeColor(leg.mode, palette)};background:${
                palette === 'dark' ? '#171B22' : '#fff'
              }">${iconHtml(MODE_META[leg.mode].icon, 20, modeColor(leg.mode, palette))}</div>`,
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
  const theme = useTheme();
  const [map, setMap] = useState<L.Map | null>(null);

  const icons = useMemo(() => {
    const primary = theme.palette.primary.main;
    const pin = paletteMode === 'dark' ? '#FF6E6E' : '#E53935';
    return {
      user: L.divIcon({
        className: 'app-div-icon',
        html: '<div class="user-dot"></div>',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      }),
      origin: L.divIcon({
        className: 'app-div-icon',
        html: `<div style="width:16px;height:16px;border-radius:50%;box-sizing:border-box;border:4px solid ${primary};background:${
          paletteMode === 'dark' ? '#0E1116' : '#fff'
        };box-shadow:0 1px 5px rgba(0,0,0,.4)"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      }),
      destination: L.divIcon({
        className: 'app-div-icon',
        html: `<div style="filter:drop-shadow(0 2px 3px rgba(0,0,0,.45))">${iconHtml(Place, 40, pin)}</div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 38],
      }),
    };
  }, [paletteMode, theme.palette.primary.main]);

  return (
    <>
      <Box sx={{ position: 'absolute', inset: 0 }}>
        <MapContainer
          ref={setMap}
          center={WARSAW}
          zoom={13}
          zoomControl={false}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            key={paletteMode}
            url={TILE_URL}
            className={`tiles-${paletteMode}`}
            maxZoom={19}
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          />
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
        </MapContainer>
      </Box>

      {/* map controls: theme, location, zoom */}
      <Box
        sx={{
          position: 'absolute',
          zIndex: 900,
          right: { xs: 12, sm: 16 },
          top: { xs: 'calc(env(safe-area-inset-top) + 156px)', sm: 'calc(env(safe-area-inset-top) + 16px)' },
          display: 'flex',
          flexDirection: 'column',
          gap: 1.5,
        }}
      >
        <Paper elevation={4} sx={{ borderRadius: '50%' }}>
          <IconButton
            aria-label={paletteMode === 'dark' ? 'Włącz jasny motyw' : 'Włącz ciemny motyw'}
            onClick={onToggleMode}
          >
            {paletteMode === 'dark' ? <LightMode /> : <DarkMode />}
          </IconButton>
        </Paper>
        <Paper elevation={4} sx={{ borderRadius: '50%' }}>
          <IconButton aria-label="Moja lokalizacja" onClick={onLocate}>
            <MyLocation color="primary" />
          </IconButton>
        </Paper>
        <Paper elevation={4} sx={{ borderRadius: 999, display: 'flex', flexDirection: 'column' }}>
          <IconButton aria-label="Przybliż" onClick={() => map?.zoomIn()}>
            <Add />
          </IconButton>
          <IconButton aria-label="Oddal" onClick={() => map?.zoomOut()}>
            <Remove />
          </IconButton>
        </Paper>
      </Box>
    </>
  );
}
