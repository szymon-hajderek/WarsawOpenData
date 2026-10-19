# fix/delay-api-url

- `fetchDelay` (`frontend/src/api/delay.ts`) builds its URL with `apiUrl()` like every other backend call, so
  `VITE_API_URL` is respected.
- Empty `API_URL` (mock mode): returns `available: false`, `reason: backend_unavailable` without a request.
- New `isBusDelay` validator in `src/api/validate.ts` (contract: `data/API.md`, `GET /api/live/delay`); a wrong
  answer shape counts as `backend_unavailable`. Vitest cases in `validate.test.ts`.
- `bus-delay` event and the 10 s polling are unchanged. No API change.
- Assumption: the plan came fully specified from the session that started this one, so the deep-planning interview was skipped.
