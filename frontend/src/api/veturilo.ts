import { API_URL, apiUrl } from '../config';

/** Live bikes and free docks of one Veturilo station (`GET /api/veturilo/status`). */
export interface DockStatus {
  bikes: number;
  docks: number;
}

const isNum = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);

/** Live status by station id as in `GET /api/stations` (`vet:203610`). Empty without a backend. */
export async function fetchVeturiloStatus(signal?: AbortSignal): Promise<Map<string, DockStatus>> {
  const out = new Map<string, DockStatus>();
  if (!API_URL) return out;
  const res = await fetch(apiUrl('/api/veturilo/status'), { signal });
  if (!res.ok) throw new Error(`Veturilo status failed: ${res.status}`);
  const data: unknown = await res.json();
  if (!Array.isArray(data)) throw new Error('Veturilo status has an unexpected shape');
  for (const s of data) {
    if (typeof s !== 'object' || s === null) continue;
    const { station_id: id, bikes, docks } = s as Record<string, unknown>;
    if (typeof id === 'string' && isNum(bikes) && isNum(docks)) out.set(`vet:${id}`, { bikes, docks });
  }
  return out;
}
