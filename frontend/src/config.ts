/**
 * Base URL of the FastAPI backend.
 *
 * - Default: `http://localhost:8000` (local dev backend).
 * - Set `VITE_API_URL` in `frontend/.env` to point elsewhere.
 * - Set `VITE_API_URL=""` to disable the backend and always use the in-browser mock.
 *
 * When the backend is unreachable, the API wrappers fall back to the mock, so the
 * UI keeps working without a running backend.
 */
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
