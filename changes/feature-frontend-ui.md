# Changes on `feature/frontend-ui`

- Added the first version of the frontend in `frontend/` (React + TypeScript + Vite, Leaflet + OpenStreetMap, Material UI).
- Screens (mobile first, also works on desktop):
  - map with the user's location + start / destination fields at the top (place search via Nominatim, limited to Warsaw),
  - list of connection options ("Wybierz trasę") with route preview on the map, travel profile (standard / slower pace / stroller & accessibility),
  - chosen route: clean route on the map with transfer markers, summary (time, distance, kcal, cost) and step list.
- Material theme in `src/theme.ts` with light and dark mode (switch on the map, follows the system setting by default).
- **Routing is mocked**: `src/api/routes.ts` (`fetchRouteOptions`) generates connections locally. Replace its body with a call to the FastAPI / OpenTripPlanner backend returning the same `RouteOption[]` (see `src/types.ts`).
- Map tiles: standard OpenStreetMap tiles (no API key); dark mode is a CSS filter. Use a proper tile provider for production.
