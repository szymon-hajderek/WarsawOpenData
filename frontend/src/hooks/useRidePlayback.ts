import { useCallback, useEffect, useRef, useState } from 'react';
import { rideDuration, sampleRide, type Ride } from '../sim/ride';

export type Speed = 1 | 10 | 60;

/** Plays a ride: elapsed seconds that advance in real time times `speed`; pause, seek, speed. */
export function useRidePlayback(ride: Ride | null) {
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(10);
  const duration = ride ? rideDuration(ride) : 0;
  const last = useRef(0);

  // A new ride starts from the beginning, paused.
  useEffect(() => {
    setElapsed(0);
    setPlaying(false);
  }, [ride]);

  useEffect(() => {
    if (!playing) return;
    last.current = performance.now();
    let frame = requestAnimationFrame(function tick(now: number) {
      const dt = (now - last.current) / 1000;
      last.current = now;
      setElapsed((e) => {
        const next = Math.min(duration, e + dt * speed);
        if (next >= duration) setPlaying(false);
        return next;
      });
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, duration]);

  const toggle = useCallback(() => {
    setElapsed((e) => (e >= duration ? 0 : e)); // play again from the start after the end
    setPlaying((p) => !p);
  }, [duration]);

  return {
    elapsed,
    duration,
    playing,
    speed,
    setSpeed,
    toggle,
    seek: (s: number) => setElapsed(Math.min(duration, Math.max(0, s))),
    sample: ride ? sampleRide(ride, elapsed) : null,
  };
}
