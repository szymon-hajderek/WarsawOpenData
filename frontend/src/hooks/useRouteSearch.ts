import { useEffect, useState } from 'react';
import { BackendOfflineError, fetchRouteOptions } from '../api/routes';
import { fetchStreetTrip, StreetRouteError } from '../api/streetRoute';
import { isStreetMode, type TravelMode } from '../travel';
import type { RouteSearchBody } from '../preferences/model';
import type { Place, RouteOption, StopOrder } from '../types';

interface Query {
  origin: Place | null;
  destination: Place | null;
  via: Place[];
  order: StopOrder;
  search?: RouteSearchBody;
  /** `transit` = the normal search; the other modes are street-only trips. */
  travel?: TravelMode;
}

/** Fetches the connections as soon as both points are set; a new query cancels the old one. */
export function useRouteSearch({ origin, destination, via, order, search, travel = 'transit' }: Query) {
  const [options, setOptions] = useState<RouteOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [offline, setOffline] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [mock, setMock] = useState(false);

  useEffect(() => {
    setError(false);
    setOffline(false);
    setErrorMessage(null);
    if (!origin || !destination) {
      setOptions([]);
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    setLoading(true);
    const request = isStreetMode(travel)
      ? fetchStreetTrip({ from: origin, to: destination, via, order }, travel, ac.signal).then((found) => ({ options: found, mock: false }))
      : fetchRouteOptions({ from: origin, to: destination, profile: 'standard', via, order, search }, ac.signal);
    request
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
        setErrorMessage(err instanceof StreetRouteError ? err.message : null);
        setError(true);
        setLoading(false);
      });
    return () => ac.abort();
  }, [origin, destination, via, order, search, travel]);

  return { options, loading, error, offline, errorMessage, mock };
}
