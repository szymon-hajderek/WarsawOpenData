import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type Ref,
} from 'react';
import { Box, Paper } from '@mui/material';
import { PANEL_BOTTOM, RADIUS } from '../layout';

/** Heights a sheet settles on: a bar, the middle (the essentials + the action) and the full sheet. */
export type SheetSnap = 'bar' | 'middle' | 'full';
export const SNAPS: SheetSnap[] = ['bar', 'middle', 'full'];
export const BAR_H = 76;
export const DEFAULT_MIDDLE_H = 258;

export function useViewport() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const onResize = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return size;
}

/** Heights in px: the middle is at most half of the screen, the full sheet 62% of it (the screen minus 200 px when wide). */
export function snapHeights(vh: number, wide: boolean, middleHeight = DEFAULT_MIDDLE_H): Record<SheetSnap, number> {
  const middle = Math.min(middleHeight, Math.round(vh * 0.5));
  const full = Math.max(middle + 90, wide ? vh - 200 : Math.round(vh * 0.62));
  return { bar: BAR_H, middle, full };
}

/** The heights for the current screen (e.g. to keep the map visible above a sheet). */
export function useSnapHeights(middleHeight = DEFAULT_MIDDLE_H) {
  const { w, h } = useViewport();
  return snapHeights(h, w >= 600, middleHeight);
}

interface DragState {
  startY: number;
  startH: number;
  lastY: number;
  lastT: number;
  /** Speed of the finger, px per ms, positive = up. */
  v: number;
  moved: boolean;
}

/**
 * The sheet follows the finger and settles on the nearest snap height; a quick flick carries it
 * further (to the next snap). A tap steps up (bar -> middle -> full); from full it steps back to the middle.
 */
function useSnapDrag(snap: SheetSnap, heights: Record<SheetSnap, number>, onSnap: (s: SheetSnap) => void) {
  const drag = useRef<DragState | null>(null);
  const [liveH, setLiveH] = useState<number | null>(null);
  const height = liveH ?? heights[snap];
  const clamp = (h: number) => Math.min(heights.full, Math.max(heights.bar, h));

  const tap = () => onSnap(snap === 'bar' ? 'middle' : snap === 'middle' ? 'full' : 'middle');

  const handlers = {
    onPointerDown: (e: ReactPointerEvent<HTMLElement>) => {
      drag.current = { startY: e.clientY, startH: height, lastY: e.clientY, lastT: performance.now(), v: 0, moved: false };
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        /* pointer is not active (e.g. a synthetic event): dragging still works */
      }
    },
    onPointerMove: (e: ReactPointerEvent<HTMLElement>) => {
      const d = drag.current;
      if (!d) return;
      const dy = d.startY - e.clientY;
      if (Math.abs(dy) > 6) d.moved = true;
      if (!d.moved) return;
      const now = performance.now();
      const dt = Math.max(1, now - d.lastT);
      d.v = 0.7 * d.v + 0.3 * ((d.lastY - e.clientY) / dt);
      d.lastY = e.clientY;
      d.lastT = now;
      setLiveH(clamp(d.startH + dy));
    },
    onPointerUp: () => {
      const d = drag.current;
      drag.current = null;
      if (!d) return;
      if (!d.moved) {
        setLiveH(null);
        tap();
        return;
      }
      const projected = clamp((liveH ?? d.startH) + d.v * 180);
      const target = SNAPS.reduce((best, s) =>
        Math.abs(heights[s] - projected) < Math.abs(heights[best] - projected) ? s : best,
      );
      setLiveH(null);
      onSnap(target);
    },
    onPointerCancel: () => {
      drag.current = null;
      setLiveH(null);
    },
    onKeyDown: (e: ReactKeyboardEvent<HTMLElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        tap();
      } else if (e.key === 'ArrowUp') onSnap(SNAPS[Math.min(2, SNAPS.indexOf(snap) + 1)]);
      else if (e.key === 'ArrowDown') onSnap(SNAPS[Math.max(0, SNAPS.indexOf(snap) - 1)]);
    },
  };

  return { handlers, height, dragging: liveH !== null };
}

export interface SheetState {
  /** Short enough to show the one-line bar instead of the title. */
  barLike: boolean;
  /** Fully open: the content scrolls. */
  full: boolean;
}

interface Props {
  snap: SheetSnap;
  onSnapChange: (snap: SheetSnap) => void;
  /** Height of the middle snap in px (at most half of the screen). */
  middleHeight?: number;
  ariaLabel: string;
  /** Content of the drag zone (below the handle): the bar line when `barLike`, else the title. */
  header: (state: SheetState) => ReactNode;
  /** Scrolling content; shown above the bar height. */
  children: ReactNode | ((state: SheetState) => ReactNode);
  /** Pinned below the header and above the scrolling content (e.g. filters); shown above the bar height. */
  toolbar?: ReactNode;
  /** Pinned below the content (e.g. the main button); shown above the bar height. */
  footer?: ReactNode;
  /** Ref of the scrolling content, e.g. to scroll the selected item into view. */
  contentRef?: Ref<HTMLDivElement>;
}

/**
 * A floating panel above the bottom bar that follows the finger and settles on three heights (bar, middle,
 * full). Drag the handle / header, tap it to step, or use Enter / the arrow keys on it.
 */
export default function SnapSheet({
  snap,
  onSnapChange,
  middleHeight,
  ariaLabel,
  header,
  children,
  toolbar,
  footer,
  contentRef,
}: Props) {
  const heights = useSnapHeights(middleHeight);
  const { handlers, height, dragging } = useSnapDrag(snap, heights, onSnapChange);
  const barLike = height < (heights.bar + heights.middle) / 2;
  const full = height >= heights.full - 4;
  const state: SheetState = { barLike, full };

  return (
    <Paper
      elevation={8}
      sx={{
        position: 'absolute',
        zIndex: 1000,
        bottom: PANEL_BOTTOM,
        left: { xs: 8, sm: 16 },
        right: { xs: 8, sm: 'auto' },
        width: { sm: 440 },
        height,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: RADIUS.sheet,
        overflow: 'hidden',
        // follows the finger without delay, settles smoothly after the release
        transition: dragging ? 'none' : 'height 0.32s cubic-bezier(0.2, 0.8, 0.2, 1)',
      }}
    >
      {/* drag zone: handle + header. Drag to resize, tap or Enter to step */}
      <Box
        {...handlers}
        role="button"
        tabIndex={0}
        aria-label={`${ariaLabel}: przeciągnij, aby zmienić wysokość`}
        aria-expanded={snap !== 'bar'}
        sx={{
          flexShrink: 0,
          touchAction: 'none',
          cursor: dragging ? 'grabbing' : 'grab',
          userSelect: 'none',
          px: 2.5,
          pb: barLike ? 1.5 : 1,
          '&:focus-visible': { outline: (t) => `2px solid ${t.palette.primary.main}`, outlineOffset: -2 },
        }}
      >
        <Box sx={{ display: 'grid', placeItems: 'center', py: 1.25 }}>
          <Box sx={{ width: 36, height: 4, borderRadius: RADIUS.pill, bgcolor: 'text.disabled', opacity: 0.5 }} />
        </Box>
        {header(state)}
      </Box>

      {!barLike && (
        <>
          {toolbar && <Box sx={{ flexShrink: 0, px: 2, pb: 0.5 }}>{toolbar}</Box>}
          <Box
            ref={contentRef}
            sx={{ flex: 1, minHeight: 0, overflowY: full && !dragging ? 'auto' : 'hidden', px: 2, pb: footer ? 1 : 2 }}
          >
            {typeof children === 'function' ? children(state) : children}
          </Box>
          {footer && <Box sx={{ flexShrink: 0, px: 2, pb: 2, pt: 0.5 }}>{footer}</Box>}
        </>
      )}
    </Paper>
  );
}
