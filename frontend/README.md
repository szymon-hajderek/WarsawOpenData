# Frontend

React + TypeScript + Vite, Leaflet + OpenStreetMap, Material UI.

```bash
npm install
npm run dev     # http://localhost:5173
npm run build   # type-check + production build
```

- `src/api/routes.ts` - routing service (currently a mock; the seam for the FastAPI / OpenTripPlanner backend)
- `src/api/geocode.ts` - place search (Nominatim)
- `src/theme.ts` - Material theme (light / dark); `src/modes.tsx` - icons and colours of transport modes
- `src/components/` - map, search card, route list and route details panels
