# feature/https-dev-geolocation

- The location button did nothing on a phone because the dev server was opened as `http://<laptop-ip>:5173`: browsers give the location only to HTTPS pages or `localhost`.
- New script `npm run dev:https` (`vite --mode https`) with `@vitejs/plugin-basic-ssl`: a self-signed certificate; open `https://<laptop-ip>:5173` on the phone and accept the warning once. The normal `npm run dev` is unchanged.
- When the page is not secure, the location snackbar says so (`geoErrorText` in `useLocationTrack.ts`) instead of the generic text.
- README and AGENTS.md describe the phone setup.
- Assumptions: a self-signed certificate is fine for development only (production needs real HTTPS); no public tunnel, because it would put the dev server on the internet.
- Not tested on a real phone (geolocation cannot be tried in the browser pane); the HTTPS server was checked to answer 200.
