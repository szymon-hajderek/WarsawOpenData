/**
 * Base URL of the FastAPI backend.
 *
 * - Default in the Vite dev server: the page's own origin. Vite proxies `/api` to the backend
 *   (`vite.config.ts`), so the app works from any address it was opened at (localhost, the laptop's IP,
 *   a phone on the same Wi-Fi) without CORS.
 * - Default in a production build and in tests: `http://localhost:8000`.
 * - Set `VITE_API_URL` in `frontend/.env` to point elsewhere.
 * - Set `VITE_API_URL=""` to switch the backend off.
 *
 * When the backend is off or unreachable, the app says so ("Nie połączono z serwerem"); there is no
 * made-up data. Only place search (offline list / Nominatim) and the local speed summary work without it.
 */
const devServer = import.meta.env.DEV && import.meta.env.MODE !== 'test' && typeof window !== 'undefined';

export const API_URL: string =
  import.meta.env.VITE_API_URL ?? (devServer ? window.location.origin : 'http://localhost:8000');

/** Full URL of a backend path (for example `/api/routes`). Every backend call goes through this. */
export const apiUrl = (path: string): string => `${API_URL}${path}`;
