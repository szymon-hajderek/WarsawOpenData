/**
 * Base URL of the FastAPI backend.
 *
 * - Default: `http://localhost:8000` (local dev backend).
 * - Set `VITE_API_URL` in `frontend/.env` to point elsewhere.
 * - Set `VITE_API_URL=""` to switch the backend off.
 *
 * When the backend is off or unreachable, the app says so ("Nie połączono z serwerem"); there is no
 * made-up data. Only place search (offline list / Nominatim) and the local speed summary work without it.
 */
export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Full URL of a backend path (for example `/api/routes`). Every backend call goes through this. */
export const apiUrl = (path: string): string => `${API_URL}${path}`;
