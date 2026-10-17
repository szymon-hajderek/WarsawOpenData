import { useEffect, useState } from 'react';
import { fetchRouteDelays } from '../api/routeDelays';
import type { RouteDelays, RouteOption } from '../types';

const REFRESH_MS = 30_000;

/** Live delays of the suggested routes: asked when the list changes, then every 30 s while it is shown. */
export function useRouteDelays(options: RouteOption[]): RouteDelays {
  const [delays, setDelays] = useState<RouteDelays>({});
  const key = options.map((o) => o.id).join('|');

  useEffect(() => {
    setDelays({});
    if (!key) return;
    const ac = new AbortController();
    const load = () => fetchRouteDelays(options, ac.signal).then((d) => !ac.signal.aborted && setDelays(d));
    void load();
    const timer = window.setInterval(load, REFRESH_MS);
    return () => {
      ac.abort();
      window.clearInterval(timer);
    };
    // `key` stands for the option ids; new objects with the same ids must not restart the polling.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return delays;
}
