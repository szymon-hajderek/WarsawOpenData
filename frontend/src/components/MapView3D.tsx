import { useEffect, useRef, useState } from 'react';
import type { GeoJSONSource, LngLatBoundsLike, Map as MlMap, Marker as MlMarker } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Box, IconButton, type PaletteMode } from '@mui/material';
import Add from '@mui/icons-material/Add';
import Remove from '@mui/icons-material/Remove';
import MyLocation from '@mui/icons-material/MyLocation';
import DarkMode from '@mui/icons-material/DarkMode';
import LightMode from '@mui/icons-material/LightMode';
import ThreeDRotation from '@mui/icons-material/ThreeDRotation';
import { ICON_PATH, iconHtml } from '../modes';
import { PALETTE } from '../map/palette';
import { MAP_ATTRIBUTION } from '../map/mapStyle';
import { createLookStyle, useMapLook } from '../map/mapLook';
import { BEARING_3D, PITCH_3D, with3dBuildings } from '../map/style3d';
import { routeGeoJson } from '../map/route3d';
import type { LatLng, Place, RouteOption } from '../types';
import type { MapPadding } from './MapView';

const WARSAW: LatLng = [52.2297, 21.0122];

interface Props {
  paletteMode: PaletteMode;
  onToggleMode: () => void;
  userPosition: LatLng | null;
  onLocate: () => void;
  origin: Place | null;
  destination: Place | null;
  route: RouteOption | null;
  padding: MapPadding;
  stops?: Place[];
  controlsOffset?: number;
  /** Back to the flat 2D map. */
  onClose3d: () => void;
}

const lonLat = (p: LatLng): [number, number] => [p[1], p[0]];

/** A round marker made of plain HTML (the 3D map has no Leaflet icons). */
function markerEl(html: string, size: number, style: string): HTMLElement {
  const el = document.createElement('div');
  el.style.cssText = `width:${size}px;height:${size}px;box-sizing:border-box;border-radius:50%;display:grid;place-items:center;${style}`;
  el.innerHTML = html;
  return el;
}

/**
 * PROTOTYPE: a tilted map with extruded buildings, drawn with MapLibre GL directly (the Leaflet map cannot tilt).
 * It shows the route, the start, the destination, the stops and the user's position. Picking a point on the map, the
 * stop overlays, popups and the follow mode of an active trip are not there; use the 2D map for those.
 */
export default function MapView3D({
  paletteMode,
  onToggleMode,
  userPosition,
  onLocate,
  origin,
  destination,
  route,
  padding,
  stops = [],
  controlsOffset = 0,
  onClose3d,
}: Props) {
  const colors = PALETTE[paletteMode];
  const [look] = useMapLook();
  const box = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MlMap | null>(null);
  const markers = useRef<MlMarker[]>([]);
  const latest = useRef({ route, paletteMode });
  latest.current = { route, paletteMode };

  /** Adds the route source and its layers (again after every style change). */
  const addRouteLayers = (m: MlMap) => {
    if (m.getSource('route')) return;
    const { route: r, paletteMode: p } = latest.current;
    m.addSource('route', {
      type: 'geojson',
      data: r ? routeGeoJson(r, p) : { type: 'FeatureCollection', features: [] },
    });
    const is = (style: string) => ['==', ['get', 'style'], style] as never;
    m.addLayer({
      id: 'route-casing',
      type: 'line',
      source: 'route',
      filter: ['==', ['get', 'casing'], true],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#FFFFFF', 'line-width': 11, 'line-opacity': 0.95 },
    });
    m.addLayer({ id: 'route-solid', type: 'line', source: 'route', filter: is('solid'), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': 6 } });
    m.addLayer({ id: 'route-dashed', type: 'line', source: 'route', filter: is('dashed'), layout: { 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': 6, 'line-dasharray': [2, 1.5] } });
    m.addLayer({ id: 'route-dotted', type: 'line', source: 'route', filter: is('dotted'), layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': ['get', 'color'], 'line-width': 5, 'line-dasharray': [0.1, 2] } });
    m.addLayer({ id: 'route-access', type: 'line', source: 'route', filter: is('access'), paint: { 'line-color': ['get', 'color'], 'line-width': 7, 'line-dasharray': [1, 2] } });
  };

  // One map for the life of the component.
  useEffect(() => {
    let cancelled = false;
    let created: MlMap | null = null;
    void import('maplibre-gl').then(({ default: maplibregl }) => {
      if (cancelled || !box.current) return;
      const style = with3dBuildings(createLookStyle(look, paletteMode), look, paletteMode);
      created = new maplibregl.Map({
        container: box.current,
        style,
        center: lonLat(userPosition ?? WARSAW),
        zoom: 15.2,
        pitch: PITCH_3D,
        bearing: BEARING_3D,
        maxPitch: 70,
        attributionControl: { compact: true, customAttribution: MAP_ATTRIBUTION },
      });
      created.on('style.load', () => created && addRouteLayers(created));
      setMap(created);
    });
    return () => {
      cancelled = true;
      markers.current.forEach((m) => m.remove());
      markers.current = [];
      created?.remove();
      setMap(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Light / dark switch (or another look): the same map, a new style.
  const first = useRef(true);
  useEffect(() => {
    if (!map) return;
    if (first.current) {
      first.current = false;
      return;
    }
    map.setStyle(with3dBuildings(createLookStyle(look, paletteMode), look, paletteMode));
  }, [map, look, paletteMode]);

  // The route on the map.
  useEffect(() => {
    const source = map?.getSource('route') as GeoJSONSource | undefined;
    source?.setData(route ? routeGeoJson(route, paletteMode) : { type: 'FeatureCollection', features: [] });
  }, [map, route, paletteMode]);

  // Markers: user, start, destination, stops.
  useEffect(() => {
    if (!map) return;
    let cancelled = false;
    void import('maplibre-gl').then(({ default: maplibregl }) => {
      if (cancelled) return;
      markers.current.forEach((m) => m.remove());
      markers.current = [];
      const add = (el: HTMLElement, position: LatLng) => {
        markers.current.push(new maplibregl.Marker({ element: el }).setLngLat(lonLat(position)).addTo(map));
      };
      const ring = `border:3px solid ${colors.surface};box-shadow:${colors.shadow}`;
      if (userPosition) add(markerEl(iconHtml(ICON_PATH.navigation, 24, colors.accent), 42, `background:${colors.surface};box-shadow:${colors.shadow}`), userPosition);
      if (origin && !origin.isCurrentLocation) add(markerEl('', 20, `border:5px solid ${colors.accent};background:${colors.surface};box-shadow:${colors.shadow}`), origin.position);
      const mid = route?.waypoints?.length ? route.waypoints.slice(1, -1) : stops;
      mid.forEach((p, i) =>
        add(markerEl(String(i + 1), 30, `${ring};background:${colors.accent};color:${colors.theme.primary.contrastText};font:700 13px/1 Roboto,sans-serif`), p.position),
      );
      if (destination) add(markerEl(iconHtml(ICON_PATH.place, 24, colors.theme.primary.contrastText), 44, `${ring};background:${colors.accent}`), destination.position);
    });
    return () => {
      cancelled = true;
    };
  }, [map, userPosition, origin, destination, stops, route, colors]);

  // Fit the view to the route (or to the two points), like the 2D map.
  useEffect(() => {
    if (!map) return;
    const points: LatLng[] = route ? route.legs.flatMap((l) => l.path) : ([origin?.position, destination?.position].filter(Boolean) as LatLng[]);
    if (points.length >= 2) {
      const lons = points.map((p) => p[1]);
      const lats = points.map((p) => p[0]);
      const bounds: LngLatBoundsLike = [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
      map.fitBounds(bounds, { padding: { top: padding.top, left: padding.left, bottom: padding.bottom, right: padding.right }, maxZoom: 16, duration: 900 });
    } else if (points.length === 1) {
      map.flyTo({ center: lonLat(points[0]), zoom: 16, duration: 900 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, route?.id, origin?.id, destination?.id, padding.top, padding.left, padding.bottom, padding.right]);

  // The first location fix centres the map (when nothing else is chosen yet).
  const centered = useRef(false);
  useEffect(() => {
    if (map && userPosition && !centered.current && !origin && !destination) {
      centered.current = true;
      map.flyTo({ center: lonLat(userPosition), zoom: 15.2, duration: 900 });
    }
  }, [map, userPosition, origin, destination]);

  const fab = (label: string, onClick: () => void, child: React.ReactNode) => (
    <Box sx={{ borderRadius: '50%', bgcolor: colors.surface, boxShadow: colors.shadow, '& .MuiIconButton-root': { width: 46, height: 46, color: colors.accent, fontWeight: 800, fontSize: 15 } }}>
      <IconButton aria-label={label} onClick={onClick}>
        {child}
      </IconButton>
    </Box>
  );

  return (
    <>
      <Box ref={box} data-testid="map-3d" sx={{ position: 'absolute', inset: 0, '& .maplibregl-ctrl-attrib': { fontSize: 10 } }} />
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
        {fab('Wróć do mapy 2D', onClose3d, '2D')}
        {fab(paletteMode === 'dark' ? 'Włącz jasny motyw' : 'Włącz ciemny motyw', onToggleMode, paletteMode === 'dark' ? <LightMode /> : <DarkMode />)}
        {fab('Moja lokalizacja', onLocate, <MyLocation />)}
        {fab('Przybliż', () => map?.zoomIn(), <Add />)}
        {fab('Oddal', () => map?.zoomOut(), <Remove />)}
        {fab('Zmień nachylenie mapy', () => map?.easeTo({ pitch: map.getPitch() > 10 ? 0 : PITCH_3D, bearing: map.getPitch() > 10 ? 0 : BEARING_3D, duration: 600 }), <ThreeDRotation />)}
      </Box>
    </>
  );
}
