# AGENTS.md

Notes for working on this repo in the Base44 sandbox. Only the non-obvious bits.

## What this is

A from-scratch fullstack demo: React + Vite frontend, FastAPI backend, PostgreSQL.
It is **not** a Base44-SDK app — there are no Base44 entities or platform APIs in
use. Postgres is the only datastore.

```
frontend/   React 18 + Vite 6 dev server (served on host port 3000)
backend/    FastAPI + SQLAlchemy 2, served by uvicorn on :8000 (internal only)
```

## Running it

```bash
docker compose -f docker-compose.base44.yml up -d --build
```

Services and order: `db` (healthy) -> `migrate` (one-shot, exits 0) -> `api`
(healthy) -> `web`. `web` waits for `api` to be healthy so the first proxied
`/api` call can't race the backend boot.

## Non-obvious things

- **Single origin.** Only host port `3000` is published. Vite proxies `/api/*`
  to `http://api:8000` inside the compose network, so there is no CORS config
  and the browser only ever talks to port 3000.
- **Dependencies install on container start, not at build time.** `api`/`migrate`
  run `pip install -r requirements.txt` and `web` runs `npm install` on startup.
  That keeps the source bind-mounted and live-reloadable; it also means the first
  boot of each service takes ~10-40s. `node_modules` lives in the
  `web_node_modules` volume so it never pollutes the bind mount.
- **Schema changes.** Tables are created by `python -m app.migrate` (SQLAlchemy
  `create_all`), run as the one-shot `migrate` service. There is no migration
  framework — after changing a model, re-run just that service:
  `docker compose -f docker-compose.base44.yml run --rm migrate`.
- **Preview host allowlist.** The platform sets
  `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS` (currently `.e2b.app`); compose passes
  it through and Vite >= 6.1 appends it to `server.allowedHosts`. If the preview
  ever shows a "Blocked request / host not allowed" page, that env var is the
  first thing to check.
- **`BASE44_PREVIEW_MODE`** is passed through to `api`/`web` but no code currently
  branches on it. Gate any future sandbox-only override on an exact `=== '1'`
  check so normal runs are unaffected.
- **No external secrets.** Everything runs locally in compose; `/run/base44/app.env`
  is empty and not referenced.

## Verifying it works

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/          # 200
curl -s http://localhost:3000/api/items                                  # seeded rows
curl -s -X POST http://localhost:3000/api/items \
  -H 'Content-Type: application/json' \
  -d '{"title":"t","description":"d"}'                                   # 201
```

Logs: `docker compose -f docker-compose.base44.yml logs <db|migrate|api|web>`.

## Tests

None yet — there is no test suite in this repo.
