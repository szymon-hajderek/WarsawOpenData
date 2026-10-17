import { apiUrl } from '../config';
import type { Place } from '../types';
import type { Ride } from '../sim/ride';

/**
 * SIMULATION (demo). These endpoints exist only when the backend runs with `SIM_SCENARIO`
 * (see data/API.md, "Simulation"). `simState()` returns null when it does not, and the demo hides itself.
 */
export interface SimState {
  scenario: string;
  title: string;
  /** Simulated Warsaw local time, ISO. */
  time: string;
}

export interface SimScenario {
  name: string;
  title: string;
  source: 'recorded' | 'gtfs';
  trip: { from: Place; to: Place; profile?: string } | null;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(apiUrl(path), init);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return (await r.json()) as T;
}

const post = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export async function simState(signal?: AbortSignal): Promise<SimState | null> {
  try {
    const r = await fetch(apiUrl('/api/sim/state'), { signal });
    return r.ok ? ((await r.json()) as SimState) : null;
  } catch {
    return null;
  }
}

export const simScenarios = () => json<SimScenario[]>('/api/sim/scenarios');

export const loadScenario = (name: string) => json<SimState>('/api/sim/scenario', post({ name }));

/** Simulate a user travelling `option`. Takes 30-60 s for a long trip. */
export const simRide = (option: unknown, profile: string, noiseM: number, signal?: AbortSignal) =>
  json<Ride>('/api/sim/ride', { ...post({ option, profile, noiseM }), signal });

