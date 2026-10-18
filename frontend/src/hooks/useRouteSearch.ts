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
  /** Warsaw local departure `YYYY-MM-DDTHH:MM`; empty = now. Sent to every kind of search. */
  when?: string;
}

/** Fetches the connections as soon as both points are set; a new query cancels the old one. */
export function useRouteSearch({ origin, destination, via, order, search, travel = 'transit', when }: Query) {
  const [options, setOptions] = useState<RouteOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [offline, setOffline] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
      ? fetchStreetTrip({ from: origin, to: destination, via, order, when }, travel, ac.signal).then((found) => ({ options: found }))
      : fetchRouteOptions({ from: origin, to: destination, profile: 'standard', via, order, search, when }, ac.signal);
    request
      .then((result) => {
        setOptions(result.options);
        setLoading(false);
      })
      .catch((err) => {
        if (ac.signal.aborted) return;
        console.warn('Route search failed', err);
        setOptions([]);
        setOffline(err instanceof BackendOfflineError);
        setErrorMessage(err instanceof StreetRouteError ? err.message : null);
        setError(true);
        setLoading(false);
      });
    return () => ac.abort();
  }, [origin, destination, via, order, search, travel, when]);

  return { options, loading, error, offline, errorMessage };
}
