import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, Polyline, TileLayer, useMap } from 'react-leaflet';
import { Box, IconButton, Paper, useTheme, type PaletteMode } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Remove from '@mui/icons-material/Remove';
import MyLocation from '@mui/icons-material/MyLocation';
import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import Place from '@mui/icons-material/Place';
import Layers from '@mui/icons-material/Layers';
import Navigation from '@mui/icons-material/Navigation';
import { MODE_META, iconHtml, modeColor } from '../modes';
import { useMapVariant, type MapVariant } from '../mapVariant';
import { createStyle, MAP_V2_ATTRIBUTION } from '../map/styleV2';
import type { LatLng, Place as PlaceT, RouteOption } from '../types';

const WARSAW: LatLng = [52.2297, 21.0122];

// Standard OpenStreetMap tiles (no API key). Dark mode is a CSS filter (see index.css).
// For production use a tile provider / self-hosted tiles, per the OSM tile usage policy.
const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

// Accent of map variant v2 (lavender) and the tint of its round markers.
const ACCENT_V2: Record<PaletteMode, string> = { light: '#7C6CF0', dark: '#A99BFF' };
const MARKER_TINT_V2: Record<PaletteMode, string> = { light: '#ECE8FF', dark: '#34304F' };
const SURFACE_V2: Record<PaletteMode, string> = { light: '#FFFFFF', dark: '#26243D' };
const SHADOW_V2 = '0 6px 18px rgba(70, 50, 190, 0.25)';

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

/** Variant v2 basemap: flat vector tiles drawn by MapLibre GL inside the Leaflet map. */
function VectorBasemap({ mode }: { mode: PaletteMode }) {
  const map = useMap();

  useEffect(() => {
    let layer: L.MaplibreGL | undefined;
    let cancelled = false;
    // The vector layer does not report its attribution to Leaflet, so add it ourselves.
    map.attributionControl.addAttribution(MAP_V2_ATTRIBUTION);
    // Loaded on demand, so variant v1 does not pay for MapLibre.
    import('@maplibre/maplibre-gl-leaflet').then(({ maplibreGL }) => {
      if (cancelled) return;
      layer = maplibreGL({
        style: createStyle(mode),
        attributionControl: false,
      }).addTo(map);
    });
    return () => {
      cancelled = true;
      map.attributionControl.removeAttribution(MAP_V2_ATTRIBUTION);
      layer?.remove();
    };
  }, [map, mode]);

  return null;
}

function RouteLayer({
  route,
  palette,
  detailed,
  variant,
}: {
  route: RouteOption;
  palette: PaletteMode;
  detailed: boolean;
  variant: MapVariant;
}) {
  const v2 = variant === 'v2';
  const casing = v2 ? SURFACE_V2[palette] : palette === 'dark' ? '#0E1116' : '#FFFFFF';

  return (
    <>
      {route.legs.map((leg, i) => {
        const walk = leg.mode === 'walk';
        const color = v2 && walk ? ACCENT_V2[palette] : modeColor(leg.mode, palette);
        return (
          <Fragment key={i}>
            {!walk && (
              <Polyline
                positions={leg.path}
                interactive={false}
                pathOptions={{ color: casing, weight: v2 ? 12 : 10, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }}
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
                className: !v2 && palette === 'dark' ? 'route-glow' : undefined,
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
            icon={
              v2
                ? L.divIcon({
                    className: 'app-div-icon',
                    iconSize: [38, 38],
                    iconAnchor: [19, 19],
                    html: `<div style="width:38px;height:38px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:3px solid ${
                      SURFACE_V2[palette]
                    };background:${MARKER_TINT_V2[palette]};box-shadow:${SHADOW_V2}">${iconHtml(
                      MODE_META[leg.mode].icon,
                      20,
                      modeColor(leg.mode, palette),
                    )}</div>`,
                  })
                : L.divIcon({
                    className: 'app-div-icon',
                    iconSize: [34, 34],
                    iconAnchor: [17, 17],
                    html: `<div class="stop-marker" style="border-color:${modeColor(leg.mode, palette)};background:${
                      palette === 'dark' ? '#171B22' : '#fff'
                    }">${iconHtml(MODE_META[leg.mode].icon, 20, modeColor(leg.mode, palette))}</div>`,
                  })
            }
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
  const { variant, toggle: toggleVariant } = useMapVariant();
  const v2 = variant === 'v2';
  const [map, setMap] = useState<L.Map | null>(null);

  const icons = useMemo(() => {
    if (variant === 'v2') {
      const accent = ACCENT_V2[paletteMode];
      const surface = SURFACE_V2[paletteMode];
      return {
        // white circle with a navigation arrow
        user: L.divIcon({
          className: 'app-div-icon',
          html: `<div style="width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:${surface};box-shadow:${SHADOW_V2}">${iconHtml(
            Navigation,
            24,
            accent,
          )}</div>`,
          iconSize: [42, 42],
          iconAnchor: [21, 21],
        }),
        origin: L.divIcon({
          className: 'app-div-icon',
          html: `<div style="width:20px;height:20px;box-sizing:border-box;border-radius:50%;border:5px solid ${accent};background:${surface};box-shadow:${SHADOW_V2}"></div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        }),
        // round accent circle with a white pin
        destination: L.divIcon({
          className: 'app-div-icon',
          html: `<div style="width:44px;height:44px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;border:3px solid ${surface};background:${accent};box-shadow:${SHADOW_V2}">${iconHtml(
            Place,
            24,
            '#FFFFFF',
          )}</div>`,
          iconSize: [44, 44],
          iconAnchor: [22, 22],
        }),
      };
    }

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
  }, [variant, paletteMode, theme.palette.primary.main]);

  // Round floating buttons: v1 keeps the Material elevation, v2 is softer and more rounded.
  const accent = ACCENT_V2[paletteMode];
  const fab = (child: ReactNode) =>
    v2 ? (
      <Box
        sx={{
          borderRadius: '50%',
          bgcolor: SURFACE_V2[paletteMode],
          boxShadow: SHADOW_V2,
          '& .MuiIconButton-root': { width: 46, height: 46, color: accent },
        }}
      >
        {child}
      </Box>
    ) : (
      <Paper elevation={4} sx={{ borderRadius: '50%' }}>
        {child}
      </Paper>
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
          {v2 ? (
            <VectorBasemap mode={paletteMode} />
          ) : (
            <TileLayer
              key={paletteMode}
              url={TILE_URL}
              className={`tiles-${paletteMode}`}
              maxZoom={19}
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
          )}
          <MapController
            origin={origin}
            destination={destination}
            route={route}
            userPosition={userPosition}
            padding={padding}
          />
          {route && <RouteLayer route={route} palette={paletteMode} detailed={detailed} variant={variant} />}
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
          gap: v2 ? 1.25 : 1.5,
        }}
      >
        {fab(
          <IconButton
            aria-label={v2 ? 'Przełącz na wygląd mapy 1' : 'Przełącz na wygląd mapy 2'}
            onClick={toggleVariant}
          >
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
            <MyLocation color={v2 ? 'inherit' : 'primary'} />
          </IconButton>,
        )}
        {v2 ? (
          <>
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
          </>
        ) : (
          <Paper elevation={4} sx={{ borderRadius: 999, display: 'flex', flexDirection: 'column' }}>
            <IconButton aria-label="Przybliż" onClick={() => map?.zoomIn()}>
              <Add />
            </IconButton>
            <IconButton aria-label="Oddal" onClick={() => map?.zoomOut()}>
              <Remove />
            </IconButton>
          </Paper>
        )}
      </Box>
    </>
  );
}
