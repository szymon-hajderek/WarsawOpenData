import { useEffect, useState } from 'react';
import { BackendOfflineError, fetchRouteOptions, VehicleNotFoundError } from '../api/routes';
import { fetchStreetTrip, StreetRouteError } from '../api/streetRoute';
import { streetMode, TRANSIT_PROFILE, type Access, type TravelMode } from '../travel';
import type { RouteSearchBody } from '../preferences/model';
import type { Place, RouteOption, StopOrder } from '../types';

interface Query {
  origin: Place | null;
  destination: Place | null;
  via: Place[];
  order: StopOrder;
  search?: RouteSearchBody;
  /** `transit` = the normal search; `walk` and `bike` are street-only trips. */
  travel?: TravelMode;
  /** Accessibility of a transit search (its `profile`) or of a walk (its `travel`); the bike ignores it. */
  access?: Access;
  /** Plan from this vehicle (the user rides it); the start is then only its label. */
  onboardVehicleId?: string | null;
  /** Warsaw local departure `YYYY-MM-DDTHH:MM`; empty = now. Sent to every kind of search. */
  when?: string;
}

/** Fetches the connections as soon as both points are set; a new query cancels the old one. */
export function useRouteSearch({ origin, destination, via, order, search, travel = 'transit', access = 'standard', onboardVehicleId = null, when }: Query) {
  const [options, setOptions] = useState<RouteOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [offline, setOffline] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  /** The backend did not know the vehicle sent as `onboard` (404): the caller plans from the GPS position. */
  const [vehicleNotFound, setVehicleNotFound] = useState(false);

  useEffect(() => {
    setError(false);
    setOffline(false);
    setErrorMessage(null);
    setVehicleNotFound(false);
    if (!origin || !destination) {
      setOptions([]);
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    setLoading(true);
    // Street trips send only `travel`: the vehicle exclusions and the search preferences are about public transport.
    const street = streetMode(travel, access);
    const request = street
      ? fetchStreetTrip({ from: origin, to: destination, via, order, when }, street, ac.signal).then((found) => ({ options: found }))
      : fetchRouteOptions(
          { from: origin, to: destination, profile: TRANSIT_PROFILE[access], via, order, search, when, onboard: onboardVehicleId ? { vehicleId: onboardVehicleId } : null },
          ac.signal,
        );
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
        setVehicleNotFound(err instanceof VehicleNotFoundError);
        setErrorMessage(err instanceof StreetRouteError ? err.message : null);
        setError(true);
        setLoading(false);
      });
    return () => ac.abort();
  }, [origin, destination, via, order, search, travel, access, onboardVehicleId, when]);

  return { options, loading, error, offline, errorMessage, vehicleNotFound };
}
