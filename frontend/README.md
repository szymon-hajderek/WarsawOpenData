# Frontend

React + TypeScript + Vite, Material UI, Leaflet + MapLibre GL (OpenFreeMap vector tiles).

```bash
npm install
npm run dev         # http://localhost:5173 (Vite proxies /api to the backend on port 8000)
npm run dev:https   # the same over HTTPS (self-signed), for geolocation on a phone
npm run build       # type-check + production build
npm run lint        # ESLint
npm test            # Vitest (jsdom); on Node 26: NODE_OPTIONS=--no-experimental-webstorage npm test
```

- `src/config.ts` - backend URL (`VITE_API_URL`, default: the page's own origin in the dev server, `http://localhost:8000` in a build; `""` = backend off, the app says "Nie połączono z serwerem")
- `src/api/routes.ts` - route search (`POST /api/routes`); says "Nie połączono z serwerem" when the backend is down
- `src/api/streetRoute.ts` - street-only trips (walk, wheelchair, stroller, own bike) through `POST /api/routes` with `travel`
- `src/api/geocode.ts` - place search (backend `GET /api/geocode`, else Nominatim + `src/data/places.json`)
- `src/theme.ts` - Material theme (light / dark) from `src/map/palette.ts`; `src/modes.tsx` - icons and colours of transport modes
- `src/components/` - map, search card, route list and route details panels, preferences page

More (all screens, conventions, pitfalls): the "Frontend" section of `../AGENTS.md`.
