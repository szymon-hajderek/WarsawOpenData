import { useEffect, useMemo, useRef, useState } from 'react';
import type L from 'leaflet';
import { fetchStations, type Station } from '../api/stations';
import { fetchVeturiloStatus, type DockStatus } from '../api/veturilo';
import { visibleKinds, type OverlayId } from '../map/overlays';

type Box = [number, number, number, number]; // min_lat, min_lon, max_lat, max_lon

const STATUS_EVERY_MS = 60_000;

const inside = (a: Box, b: Box) => a[0] >= b[0] && a[1] >= b[1] && a[2] <= b[2] && a[3] <= b[3];

/**
 * Stations of the switched-on overlays in the visible part of the map (loaded for the view plus a margin, again only
 * when the view leaves it), and the live Veturilo status while Veturilo is shown. Failures leave the overlay empty.
 */
export function useMapOverlays(map: L.Map | null, ids: OverlayId[]) {
  const [view, setView] = useState<{ zoom: number; box: Box } | null>(null);
  const [loaded, setLoaded] = useState<{ box: Box; stations: Station[] } | null>(null);
  const [status, setStatus] = useState<Map<string, DockStatus>>(new Map());
  const timer = useRef<number>();

  // Follow the map view (debounced).
  useEffect(() => {
    if (!map) return;
    const read = () => {
      const b = map.getBounds();
      setView({ zoom: map.getZoom(), box: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()] });
    };
    const onMove = () => {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(read, 300);
    };
    read();
    map.on('moveend', onMove);
    return () => {
      map.off('moveend', onMove);
      window.clearTimeout(timer.current);
    };
  }, [map]);

  const kinds = useMemo(() => (view ? visibleKinds(ids, view.zoom) : new Set<string>()), [ids, view]);
  const any = kinds.size > 0;

  // Load the stations around the view when it leaves the loaded box.
  useEffect(() => {
    if (!view || !any || (loaded && inside(view.box, loaded.box))) return;
    const [s, w, n, e] = view.box;
    const dy = (n - s) * 0.3;
    const dx = (e - w) * 0.3;
    const box: Box = [s - dy, w - dx, n + dy, e + dx];
    const ctl = new AbortController();
    fetchStations(box, ctl.signal)
      .then((stations) => setLoaded({ box, stations }))
      .catch(() => {
        /* no overlay this time; the next move tries again */
      });
    return () => ctl.abort();
  }, [view, any, loaded]);

  // Live Veturilo status while Veturilo is shown.
  const vet = kinds.has('veturilo');
  useEffect(() => {
    if (!vet) return;
    const ctl = new AbortController();
    const load = () =>
      fetchVeturiloStatus(ctl.signal)
        .then(setStatus)
        .catch(() => {
          /* keep the last status */
        });
    void load();
    const id = window.setInterval(load, STATUS_EVERY_MS);
    return () => {
      window.clearInterval(id);
      ctl.abort();
    };
  }, [vet]);

  const stations = useMemo(
    () => (any && loaded ? loaded.stations.filter((st) => kinds.has(st.kind)) : []),
    [any, loaded, kinds],
  );
  return { stations, status, zoom: view?.zoom ?? 0 };
}
