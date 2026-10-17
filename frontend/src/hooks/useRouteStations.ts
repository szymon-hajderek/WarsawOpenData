import { useEffect, useState } from 'react';
import { fetchStation, type Station } from '../api/stations';
import type { RouteOption } from '../types';
import { stationIds } from '../utils/overlay';

const known = new Map<string, Station>();
const NONE: ReadonlyMap<string, Station> = new Map();

/**
 * The stations a route names (`fromId` / `toId` of its legs), by id. They are fetched once and kept for the
 * session. When the server has none (or does not answer) the map is simply empty: the overlay is optional and
 * nothing is made up.
 */
export function useRouteStations(route: RouteOption | null): ReadonlyMap<string, Station> {
  const ids = stationIds(route);
  const key = ids.join('|');
  const [stations, setStations] = useState<ReadonlyMap<string, Station>>(NONE);

  useEffect(() => {
    if (ids.length === 0) {
      setStations(NONE);
      return;
    }
    const ac = new AbortController();
    const have = () => new Map(ids.flatMap((id) => (known.has(id) ? [[id, known.get(id)!] as const] : [])));
    setStations(have());
    const missing = ids.filter((id) => !known.has(id));
    if (missing.length > 0) {
      Promise.all(
        missing.map((id) =>
          fetchStation(id, ac.signal)
            .then((s) => {
              if (s) known.set(id, s);
            })
            .catch(() => undefined),
        ),
      ).then(() => {
        if (!ac.signal.aborted) setStations(have());
      });
    }
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return stations;
}
