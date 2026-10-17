import { useEffect, useState } from 'react';
import { BackendOfflineError, fetchRouteOptions } from '../api/routes';
import type { RouteSearchBody } from '../preferences/model';
import type { Place, RouteOption, StopOrder } from '../types';

interface Query {
  origin: Place | null;
  destination: Place | null;
  via: Place[];
  order: StopOrder;
  search?: RouteSearchBody;
}

/** Fetches the connections as soon as both points are set; a new query cancels the old one. */
export function useRouteSearch({ origin, destination, via, order, search }: Query) {
  const [options, setOptions] = useState<RouteOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [offline, setOffline] = useState(false);
  const [mock, setMock] = useState(false);

  useEffect(() => {
    setError(false);
    setOffline(false);
    if (!origin || !destination) {
      setOptions([]);
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    setLoading(true);
    fetchRouteOptions({ from: origin, to: destination, profile: 'standard', via, order, search }, ac.signal)
      .then((result) => {
        setOptions(result.options);
        setMock(result.mock);
        setLoading(false);
      })
      .catch((err) => {
        if (ac.signal.aborted) return;
        console.warn('Route search failed', err);
        setOptions([]);
        setMock(false);
        setOffline(err instanceof BackendOfflineError);
        setError(true);
        setLoading(false);
      });
    return () => ac.abort();
  }, [origin, destination, via, order, search]);

  return { options, loading, error, offline, mock };
}
