# fix/api-same-origin

- Frontend: in the Vite dev server the API base defaults to the page's own origin (Vite proxies `/api`), so the app
  works from any address (localhost, the laptop's IP, a phone). A fixed `VITE_API_URL=https://<ip>:5173` made
  every other address fail with "Nie połączono z serwerem" (cross-origin calls blocked).
- Build and tests keep the `http://localhost:8000` default; `VITE_API_URL` still overrides; `""` = backend off.
