import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react';
import { Box, Button, Chip, IconButton, Paper, ToggleButton, ToggleButtonGroup, useTheme, type SxProps, type Theme } from '@mui/material';
import SwapVert from '@mui/icons-material/SwapVert';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import TripOriginIcon from '@mui/icons-material/TripOrigin';
import PlaceIcon from '@mui/icons-material/Place';
import Add from '@mui/icons-material/Add';
import Close from '@mui/icons-material/Close';
import DragIndicator from '@mui/icons-material/DragIndicator';
import PlaceField from './PlaceField';
import DepartureControl from './DepartureControl';
import { useSheetDock } from './SnapSheet';
import type { Departure } from '../utils/departure';
import { MAX_STOPS } from '../api/routes';
import type { Place, StopOrder } from '../types';
import { RADIUS } from '../layout';
import { ACCESS_LABELS, ACCESS_OPTIONS, hasAccess, TRAVEL_LABELS, TRAVEL_MODES, type Access, type TransitAccess, type TravelMode } from '../travel';
import TransitAccessToggle from './TransitAccessToggle';
import { PALETTE } from '../map/palette';

/** Colour between `a` and `b` (hex), `t` in 0..1. */
function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t));
  return `#${c.map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}

/** Which field a point picked on the map fills: the start, the destination or stop `n` (0-based). */
export type PickTarget = 'origin' | 'destination' | number;

interface Props {
  origin: Place | null;
  destination: Place | null;
  /** Intermediate stops; `null` = an empty field the user has just added. */
  stops: (Place | null)[];
  order: StopOrder;
  /** How the user wants to travel (public transport or a street-only trip). */
  travel?: TravelMode;
  /** Without it the row of travel modes is not shown (the ride demo). */
  onTravelChange?: (mode: TravelMode) => void;
  /** Accessibility of a transit or walking search ("Pieszo" / "Na wózku" / "Z wózkiem dziecięcym"); not shown for the bike. */
  access?: Access;
  onAccessChange?: (access: Access) => void;
  /** Public transport only: the "Z własnym rowerem" switch (own bike to / from / between stops; hides the accessibility choice). */
  transitAccess?: TransitAccess;
  onTransitAccessChange?: (access: TransitAccess) => void;
  /** Departure time (`null` = now). Without `onDepartureChange` the control is not shown (the ride demo). */
  departure?: Departure;
  onDepartureChange?: (d: Departure) => void;
  currentLocation: Place | null;
  onOriginChange: (p: Place | null) => void;
  onDestinationChange: (p: Place | null) => void;
  onStopsChange: (stops: (Place | null)[]) => void;
  onOrderChange: (order: StopOrder) => void;
  /** Reverses the whole trip (start <-> destination, stops in reverse). */
  onSwap: () => void;
  onLocate: () => void;
  /** Phone: the card shows only "Dokąd jedziesz?" until the chevron opens it. Without `onToggleCollapsed` it is always open. */
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  /** Active trip: a "Wróć do przejazdu" button on top leaves the new search without changing the route. */
  onBackToTrip?: () => void;
  /** Offers "Wybierz na mapie" in every place field. */
  onPickOnMap?: (target: PickTarget) => void;
}

/** One row of the timeline column: a gradient segment above and below the icon. */
function TimelineCell({
  from,
  to,
  fromT,
  midT,
  toT,
  first,
  last,
  icon,
}: {
  from: string;
  to: string;
  fromT: number;
  midT: number;
  toT: number;
  first: boolean;
  last: boolean;
  icon: ReactNode;
}) {
  const at = (t: number) => mix(from, to, t);
  const segment = (a: number, b: number, visible: boolean) => (
    <Box
      sx={{
        flex: 1,
        width: 3,
        borderRadius: RADIUS.pill,
        background: visible ? `linear-gradient(to bottom, ${at(a)}, ${at(b)})` : 'transparent',
      }}
    />
  );
  return (
    <Box aria-hidden sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 24, py: 0.25 }}>
      {segment(fromT, midT, !first)}
      <Box sx={{ my: 0.25, display: 'grid', placeItems: 'center' }}>{icon}</Box>
      {segment(midT, toT, !last)}
    </Box>
  );
}

/** Card at the top of the screen: start, intermediate stops and destination. */
export default function SearchCard({
  origin,
  destination,
  stops,
  order,
  travel = 'transit',
  onTravelChange,
  access = 'standard',
  onAccessChange,
  transitAccess = 'walk',
  onTransitAccessChange,
  departure = null,
  onDepartureChange,
  currentLocation,
  onOriginChange,
  onDestinationChange,
  onStopsChange,
  onOrderChange,
  onSwap,
  onLocate,
  collapsed = false,
  onToggleCollapsed,
  onBackToTrip,
  onPickOnMap,
}: Props) {
  const { routeStart, routeEnd } = PALETTE[useTheme().palette.mode];
  const count = stops.length + 2; // rows: start, stops, destination
  const t = (row: number) => Math.min(1, Math.max(0, row / (count - 1)));
  const filledStops = stops.filter(Boolean).length;

  const setStop = (i: number, place: Place | null) => onStopsChange(stops.map((s, k) => (k === i ? place : s)));
  // ---- reordering the stops: drag the handle (or use the arrow keys on it) at any time, filled or empty
  const rowRefs = useRef<(HTMLElement | null)[]>([]);
  const handleRefs = useRef<(HTMLElement | null)[]>([]);
  const startY = useRef(0);
  const [drag, setDrag] = useState<{ from: number; to: number; offset: number; rowH: number } | null>(null);
  const [focusStop, setFocusStop] = useState<number | null>(null);

  // Rows are [start, ...stops, destination]; any row can be moved to any position, so a stop can become
  // the start or the destination and the other way round.
  const reorder = (from: number, to: number) => {
    if (from === to) return;
    const rows = [origin, ...stops, destination];
    const [item] = rows.splice(from, 1);
    rows.splice(to, 0, item);
    onOriginChange(rows[0]);
    onStopsChange(rows.slice(1, -1));
    onDestinationChange(rows[rows.length - 1]);
    // moving a row by hand means the user wants their own order
    if (order !== 'given') onOrderChange('given');
  };

  // keep the keyboard focus on the handle of the stop that was moved
  useEffect(() => {
    if (focusStop === null) return;
    handleRefs.current[focusStop]?.focus();
    setFocusStop(null);
  }, [focusStop, stops, origin, destination]);

  const onHandleDown = (i: number, e: ReactPointerEvent<HTMLElement>) => {
    startY.current = e.clientY;
    setDrag({ from: i, to: i, offset: 0, rowH: rowRefs.current[i]?.offsetHeight ?? 56 });
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* pointer is not active (e.g. a synthetic event): dragging still works */
    }
  };
  const onHandleMove = (e: ReactPointerEvent<HTMLElement>) => {
    if (!drag) return;
    const offset = e.clientY - startY.current;
    const to = Math.min(count - 1, Math.max(0, Math.round(drag.from + offset / drag.rowH)));
    setDrag({ ...drag, offset, to });
  };
  const endDrag = (commit: boolean) => {
    if (drag && commit) reorder(drag.from, drag.to);
    setDrag(null);
  };
  const onHandleKey = (i: number, e: ReactKeyboardEvent<HTMLElement>) => {
    const to = e.key === 'ArrowUp' ? i - 1 : e.key === 'ArrowDown' ? i + 1 : i;
    if (to === i || to < 0 || to >= count) return;
    e.preventDefault();
    reorder(i, to);
    setFocusStop(to);
  };

  /** Vertical shift of a row while another one is dragged: the rows it passes make room. */
  const shift = (i: number) => {
    if (!drag) return 0;
    if (i === drag.from) return drag.offset;
    if (drag.to > drag.from && i > drag.from && i <= drag.to) return -drag.rowH;
    if (drag.to < drag.from && i >= drag.to && i < drag.from) return drag.rowH;
    return 0;
  };


  const rowName = (index: number) => (index === 0 ? 'Start' : index === count - 1 ? 'Cel' : `Przystanek ${index}`);

  /** Handle that drags a row (also usable with ArrowUp / ArrowDown); nothing to reorder without stops. */
  const handle = (index: number) =>
    stops.length === 0 ? null : (
      <IconButton
        size="small"
        ref={(el) => {
          handleRefs.current[index] = el;
        }}
        aria-label={`${rowName(index)} (pozycja ${index + 1} z ${count}): przeciągnij albo użyj strzałek w górę i w dół, aby zmienić kolejność`}
        onPointerDown={(e) => onHandleDown(index, e)}
        onPointerMove={onHandleMove}
        onPointerUp={() => endDrag(true)}
        onPointerCancel={() => endDrag(false)}
        onKeyDown={(e) => onHandleKey(index, e)}
        sx={{ touchAction: 'none', cursor: drag?.from === index ? 'grabbing' : 'grab', color: 'text.secondary' }}
      >
        <DragIndicator fontSize="small" />
      </IconButton>
    );

  /** Same width as the remove button, so the handles of all rows line up. */
  const spacer = stops.length === 0 ? null : <Box sx={{ width: 34, flexShrink: 0 }} />;

  const rowExtra = (index: number) => ({
    ref: (el: HTMLElement | null) => {
      rowRefs.current[index] = el;
    },
    sx: {
      position: 'relative',
      zIndex: drag?.from === index ? 3 : 0,
      transform: `translateY(${shift(index)}px)`,
      transition: drag && drag.from !== index ? 'transform 0.15s ease' : 'none',
      ...(drag?.from === index && {
        bgcolor: 'background.paper',
        borderRadius: RADIUS.tile,
        boxShadow: 6,
      }),
    },
  });

  const row = (
    index: number,
    icon: ReactNode,
    field: ReactNode,
    actions?: ReactNode,
    extra?: { ref?: (el: HTMLElement | null) => void; sx?: object },
  ) => (
    <Box key={index} ref={extra?.ref} sx={{ display: 'flex', alignItems: 'stretch', gap: 1, ...extra?.sx }}>
      <TimelineCell
        from={routeStart}
        to={routeEnd}
        fromT={t(index - 1)}
        midT={t(index)}
        toT={t(index + 1)}
        first={index === 0}
        last={index === count - 1}
        icon={icon}
      />
      <Box sx={{ flex: 1, minWidth: 0, py: 0.5 }}>{field}</Box>
      {actions}
    </Box>
  );

  // In the desktop side panel the card is the first block of the panel's column, not a floating card.
  const docked = useSheetDock();

  const paperSx: SxProps<Theme> = {
    position: 'absolute',
    zIndex: 1000,
    top: 'calc(env(safe-area-inset-top) + 12px)',
    left: { xs: 12, sm: 16 },
    right: { xs: 12, sm: 'auto' },
    width: { sm: 440 },
    maxHeight: 'calc(100vh - 220px)',
    overflowY: 'auto',
    p: 1.5,
    borderRadius: RADIUS.sheet,
    display: 'flex',
    alignItems: 'stretch',
    gap: 1,
    ...(docked && { position: 'static', width: 'auto', maxHeight: 'none', flexShrink: 0, borderRadius: RADIUS.card }),
  };

  // The main travel mode chips and the own-bike switch: in the open card and, so they are never hidden, in the folded one.
  const travelChips = onTravelChange && (
    <Box role="group" aria-label="Sposób podróży" sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, pt: 1, pb: 0.25 }}>
      {TRAVEL_MODES.map((m) => (
        <Chip
          key={m}
          label={TRAVEL_LABELS[m]}
          size="small"
          clickable
          color={travel === m ? 'primary' : 'default'}
          variant={travel === m ? 'filled' : 'outlined'}
          aria-pressed={travel === m}
          onClick={() => onTravelChange(m)}
        />
      ))}
    </Box>
  );
  const bikeToggle = onTravelChange && travel === 'transit' && onTransitAccessChange && (
    <TransitAccessToggle value={transitAccess} onChange={onTransitAccessChange} />
  );

  // Collapsed (phone): "Dokąd jedziesz?" plus the travel mode chips and the own-bike switch. The chevron opens the
  // whole card (start, stops, departure, accessibility).
  if (collapsed && onToggleCollapsed && !onBackToTrip) {
    return (
      <Paper
        elevation={docked ? 0 : 4}
        variant={docked ? 'outlined' : 'elevation'}
        sx={{ ...paperSx, p: 1.25, alignItems: 'flex-start' }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <PlaceField
            value={destination}
            onChange={onDestinationChange}
            placeholder="Dokąd jedziesz?"
            currentLocation={currentLocation}
          />
          {destination && !origin && (
            <Button size="small" onClick={onToggleCollapsed} sx={{ mt: 0.5 }}>
              Ustaw start
            </Button>
          )}
          {travelChips}
          {bikeToggle}
        </Box>
        <IconButton aria-label="Rozwiń wyszukiwanie: start, przystanki, sposób podróży" aria-expanded={false} onClick={onToggleCollapsed}>
          <ExpandMore />
        </IconButton>
      </Paper>
    );
  }

  return (
    <Paper
      elevation={docked ? 0 : 4}
      variant={docked ? 'outlined' : 'elevation'}
      sx={paperSx}
    >
      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {onBackToTrip && (
          <Button size="small" onClick={onBackToTrip} sx={{ alignSelf: 'flex-start', mb: 0.5 }}>
            ← Wróć do przejazdu
          </Button>
        )}
        {row(
          0,
          <TripOriginIcon sx={{ fontSize: 20, color: routeStart }} />,
          <PlaceField
            value={origin}
            onChange={onOriginChange}
            placeholder="Skąd jedziesz?"
            currentLocation={currentLocation}
            showLocateButton
            onLocate={onLocate}
            onPickOnMap={onPickOnMap && (() => onPickOnMap('origin'))}
          />,
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {handle(0)}
            {spacer}
          </Box>,
          rowExtra(0),
        )}

        {stops.map((stop, i) =>
          row(
            i + 1,
            <Box
              sx={{
                width: 18,
                height: 18,
                borderRadius: '50%',
                display: 'grid',
                placeItems: 'center',
                fontSize: 11,
                fontWeight: 700,
                color: '#fff',
                bgcolor: mix(routeStart, routeEnd, t(i + 1)),
              }}
            >
              {i + 1}
            </Box>,
            <PlaceField
              value={stop}
              onChange={(p) => setStop(i, p)}
              placeholder={`Przystanek ${i + 1}`}
              currentLocation={currentLocation}
              // eslint-disable-next-line jsx-a11y/no-autofocus -- the field is added by the user's own click
              autoFocus={stop === null}
              onPickOnMap={onPickOnMap && (() => onPickOnMap(i))}
            />,
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              {handle(i + 1)}
              <IconButton
                size="small"
                aria-label={`Usuń przystanek ${i + 1}`}
                onClick={() => onStopsChange(stops.filter((_, k) => k !== i))}
              >
                <Close fontSize="small" />
              </IconButton>
            </Box>,
            rowExtra(i + 1),
          ),
        )}

        {row(
          count - 1,
          <PlaceIcon sx={{ fontSize: 22, color: routeEnd }} />,
          <PlaceField
            value={destination}
            onChange={onDestinationChange}
            placeholder="Dokąd jedziesz?"
            currentLocation={currentLocation}
            onPickOnMap={onPickOnMap && (() => onPickOnMap('destination'))}
          />,
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {handle(count - 1)}
            {spacer}
          </Box>,
          rowExtra(count - 1),
        )}

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', pl: 4.5, pt: 0.5 }}>
          {onDepartureChange && <DepartureControl value={departure} onChange={onDepartureChange} />}
          {stops.length < MAX_STOPS && (
            <Button size="small" startIcon={<Add />} onClick={() => onStopsChange([...stops, null])}>
              Dodaj przystanek
            </Button>
          )}
          {filledStops >= 2 && (
            <ToggleButtonGroup
              exclusive
              size="small"
              value={order}
              aria-label="Kolejność przystanków"
              onChange={(_, v: StopOrder | null) => v && onOrderChange(v)}
              sx={{ '& .MuiToggleButton-root': { py: 0.25, px: 1.25, fontSize: 12 } }}
            >
              <ToggleButton value="given">Moja kolejność</ToggleButton>
              <ToggleButton value="optimal">Optymalna</ToggleButton>
            </ToggleButtonGroup>
          )}
        </Box>

        {travelChips}

        {bikeToggle}

        {onTravelChange && onAccessChange && hasAccess(travel) && !(travel === 'transit' && transitAccess === 'bike') && (
          <ToggleButtonGroup
            exclusive
            size="small"
            value={access}
            aria-label="Dostępność"
            onChange={(_, v: Access | null) => v && onAccessChange(v)}
            sx={{ mt: 0.75, '& .MuiToggleButton-root': { py: 0.25, px: 1.25, fontSize: 12 } }}
          >
            {ACCESS_OPTIONS.map((a) => (
              <ToggleButton key={a} value={a}>
                {ACCESS_LABELS[a]}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        )}
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-between' }}>
        {onToggleCollapsed ? (
          <IconButton aria-label="Zwiń wyszukiwanie" aria-expanded onClick={onToggleCollapsed}>
            <ExpandLess />
          </IconButton>
        ) : (
          <span />
        )}
        <IconButton
          aria-label={stops.length ? 'Odwróć trasę' : 'Zamień start z celem'}
          onClick={onSwap}
          disabled={!origin && !destination}
        >
          <SwapVert />
        </IconButton>
        <span />
      </Box>
    </Paper>
  );
}
