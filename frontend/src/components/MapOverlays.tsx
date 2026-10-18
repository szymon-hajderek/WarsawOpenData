import { useMemo } from 'react';
import L from 'leaflet';
import { CircleMarker, Marker, Popup, useMap } from 'react-leaflet';
import { Box, Button, Typography, type PaletteMode } from '@mui/material';
import type { Station } from '../api/stations';
import type { DockStatus } from '../api/veturilo';
import { modeColor } from '../modes';
import type { Place, TransportMode } from '../types';

const KIND_MODE: Record<string, TransportMode> = {
  bus_post: 'bus',
  tram_post: 'tram',
  metro_platform: 'metro',
  rail_platform: 'rail',
  rail_station: 'rail',
  veturilo: 'veturilo',
};

/** "Grójecka 02", "Warszawa Śródmieście peron 1/2"; Veturilo numbers are not shown. */
export function stationLabel(s: Station): string {
  return s.code && s.kind !== 'veturilo' ? `${s.name} ${s.code}` : s.name;
}

/** The station as a start / destination of a search. */
export function stationPlace(s: Station): Place {
  return {
    id: s.id,
    label: stationLabel(s),
    sublabel: s.kind === 'veturilo' ? 'Stacja Veturilo' : 'Przystanek',
    position: s.position,
  };
}

interface Props {
  stations: Station[];
  status: Map<string, DockStatus>;
  paletteMode: PaletteMode;
  /** Fills start / destination with the station; without it the popup has no buttons (active trip). */
  onPlacePick?: (target: 'origin' | 'destination', place: Place) => void;
}

function StationPopup({ station, dock, onPlacePick }: { station: Station; dock?: DockStatus } & Pick<Props, 'onPlacePick'>) {
  const map = useMap();
  const pick = (target: 'origin' | 'destination') => {
    map.closePopup();
    onPlacePick?.(target, stationPlace(station));
  };
  return (
    <Popup>
      <Box sx={{ minWidth: 170 }}>
        <Typography variant="subtitle2">{stationLabel(station)}</Typography>
        {station.kind === 'veturilo' && (
          <Typography variant="body2" color="text.secondary">
            {dock ? `Rowery: ${dock.bikes} · wolne stojaki: ${dock.docks}` : 'Brak danych na żywo'}
          </Typography>
        )}
        {onPlacePick && (
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <Button size="small" variant="outlined" onClick={() => pick('origin')}>
              Stąd
            </Button>
            <Button size="small" variant="contained" disableElevation onClick={() => pick('destination')}>
              Dotąd
            </Button>
          </Box>
        )}
      </Box>
    </Popup>
  );
}

/** Veturilo pill with the number of bikes (grey when none, "–" without live data). */
function dockIcon(count: number | null, color: string): L.DivIcon {
  const bg = count === 0 ? '#9E9E9E' : color;
  return L.divIcon({
    className: 'app-div-icon',
    html: `<div style="min-width:22px;height:20px;padding:0 5px;box-sizing:border-box;border-radius:10px;border:2px solid #fff;background:${bg};color:#fff;font:600 11px/16px system-ui,sans-serif;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.35)">${count ?? '–'}</div>`,
    iconSize: [26, 20],
    iconAnchor: [13, 10],
  });
}

/** Pills are shared by every station with the same count. */
const DOCK_ICONS = new Map<string, L.DivIcon>();

/** Stops (small dots in the mode colour) and Veturilo stations (bike count) of the switched-on overlays. */
export function MapOverlays({ stations, status, paletteMode, onPlacePick }: Props) {
  const renderer = useMemo(() => L.canvas({ padding: 0.3 }), []);
  const vetColor = modeColor('veturilo', paletteMode);
  const iconFor = (n: number | null) => {
    const key = `${vetColor}:${n}`;
    let icon = DOCK_ICONS.get(key);
    if (!icon) DOCK_ICONS.set(key, (icon = dockIcon(n, vetColor)));
    return icon;
  };

  return (
    <>
      {stations.map((s) => {
        if (s.kind === 'veturilo') {
          const dock = status.get(s.id);
          return (
            <Marker key={s.id} position={s.position} icon={iconFor(dock ? dock.bikes : null)} zIndexOffset={-500}>
              <StationPopup station={s} dock={dock} onPlacePick={onPlacePick} />
            </Marker>
          );
        }
        const big = s.kind !== 'bus_post' && s.kind !== 'tram_post';
        return (
          <CircleMarker
            key={s.id}
            center={s.position}
            radius={big ? 6 : 4.5}
            pathOptions={{ color: '#fff', weight: 1.5, fillColor: modeColor(KIND_MODE[s.kind] ?? 'bus', paletteMode), fillOpacity: 1, renderer } as L.PathOptions}
          >
            <StationPopup station={s} onPlacePick={onPlacePick} />
          </CircleMarker>
        );
      })}
    </>
  );
}
