# API keys and access

Key values live only in `.env` (git-ignored locally). Never paste a key into a file, a commit, or a chat.
`.env.example` lists the variable names.

| Variable | Service | Where to get it | How to send it | Status (2026-10-17) |
|---|---|---|---|---|
| `WAW_API_KEY` | `api.um.warszawa.pl` (ZTM live buses/trams, timetables) | api.um.warszawa.pl → Logowanie → Rejestracja konta (login only, no personal data) | query string `&apikey=<key>` | works |
| `PORTAL_KEY` | `dane.um.warszawa.pl` (open data portal, JWT) | dane.um.warszawa.pl/pl/key-api (nickname + reCAPTCHA) | header `Authorization: <key>` (no `Bearer`) | works |
| `PLK_KEY` | PKP PLK Open Data API (SKM, Koleje Mazowieckie) | pdp-api.plk-sa.pl → "Formularz Wniosku" (email verification) | header `X-API-Key: <key>` or `Authorization: Bearer <key>` | requested 2026-10-11, pending admin activation; not tested |

## Examples

```bash
set -a; source .env; set +a

# ZTM live buses (type=1 bus, type=2 tram)
curl -sL -X POST "https://api.um.warszawa.pl/api/action/busestrams_get/?resource_id=f2e5503e-927d-4ad3-9500-4ab9e55deb59&type=1&apikey=$WAW_API_KEY"

# Open data portal
curl -s -X POST https://dane.um.warszawa.pl/api/action/get_ztm_lokalizacja_pojazdow -H "Authorization: $PORTAL_KEY" -H "Content-Type: application/json" -d '{"type":1}'

# PKP PLK operations for KM and SKM
curl -s -H "X-API-Key: $PLK_KEY" "https://pdp-api.plk-sa.pl/api/v1/operations?carriersInclude=KM,SKM&withPlanned=true"
```

## Rules

- PLK: do not share the key with third parties. Call PLK from the server only.
- PLK: credit "PKP Polskie Linie Kolejowe S.A." when you publish its data.
- PLK: the Basic tier allows 100 calls per hour. PLK decides the tier. SLA target is 98% per month.
- PLK docs: https://pdp-api.plk-sa.pl/api-documentation. Contact: pdp-api@plk-sa.pl.
- Without a PLK key, SKM and KM live data is available from `https://mkuran.pl/gtfs/polish_trains/updates.pb` (unofficial mirror, can stall).
- A bad `apikey` on `api.um.warszawa.pl` returns `Bledny apikey lub jego brak`.
- `.env` is excluded through `.git/info/exclude`. If you clone the repo elsewhere, add `.env` to `.gitignore` first.
