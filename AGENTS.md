# AGENTS.md

Notes for working on this repo in the Base44 sandbox. Only the non-obvious bits.

## What this is

A digital document signing and verification service: React + Vite frontend,
FastAPI backend, PostgreSQL. It is **not** a Base44-SDK app — there are no Base44
entities or platform APIs in use.

```
frontend/   React 18 + Vite 6 dev server (served on host port 3000)
backend/    FastAPI + SQLAlchemy 2, served by uvicorn on :8000 (internal only)
```

Domain: a `Document` is uploaded, hashed (SHA-256), and gets a unique signing
`token`. A `Signature` binds three layers to that hash — an acknowledgement
record (name/email/time/IP), an HMAC-SHA256 signature keyed with the service
secret, and an RSA/X.509 signature. The service keypair, self-signed certificate
and HMAC secret live in the single-row `signing_keys` table, generated once by
`migrate` so signatures survive restarts.

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
- **Uploaded files are private**, stored on the `uploads` volume at
  `/data/documents` (env `STORAGE_DIR`) and reachable only through the API by
  signing token — there is no public URL. Uploads are capped by
  `MAX_UPLOAD_BYTES` (25 MB default).
- **Dependencies install on container start, not at build time.** `api`/`migrate`
  run `pip install -r requirements.txt` and `web` runs `npm install` on startup.
  That keeps the source bind-mounted and live-reloadable; it also means the first
  boot of each service takes ~10-40s. `node_modules` lives in the
  `web_node_modules` volume so it never pollutes the bind mount.
- **Schema changes.** Tables are created by `python -m app.migrate` (SQLAlchemy
  `create_all`), run as the one-shot `migrate` service. There is no migration
  framework — after changing a model, re-run just that service:
  `docker compose -f docker-compose.base44.yml run --rm migrate`.
- **Routing is path-based, not a router library.** `frontend/src/App.jsx` reads
  `window.location.pathname` and renders `Home`, `SignPage` (`/sign/<token>`) or
  `VerifyPage` (`/verify`). Navigation uses real `<a href>` links, so each page
  change is a full document load — Vite's default SPA fallback serves
  `index.html` for those paths. Because the app reads the path only at mount, a
  client-side `history.pushState` will NOT switch pages; use a real navigation.
- **Preview host allowlist.** The platform sets
  `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS` (currently `.e2b.app`); compose passes
  it through and Vite >= 6.1 appends it to `server.allowedHosts`. If the preview
  ever shows a "Blocked request / host not allowed" page, that env var is the
  first thing to check.
- **`BASE44_PREVIEW_MODE`** is passed through to `api`/`web` but no code currently
  branches on it. Gate any future sandbox-only override on an exact `=== '1'`
  check so normal runs are unaffected.
- **No external secrets.** Everything runs locally in compose; `/run/base44/app.env`
  is empty and not referenced. The signing key material is generated locally into
  Postgres, not read from the environment.

## Verifying it works

```bash
# upload -> returns a token
TOKEN=$(curl -s -F "file=@/tmp/doc.txt" http://localhost:3000/api/documents \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')

# sign, then confirm a second signature is rejected with 409
curl -s -X POST http://localhost:3000/api/documents/$TOKEN/sign \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada Lovelace","email":"ada@example.com"}'

# verify: the untouched file returns "verified": true,
# any edited copy returns "matched": false
curl -s -F "file=@/tmp/doc.txt" http://localhost:3000/api/verify
```

Logs: `docker compose -f docker-compose.base44.yml logs <db|migrate|api|web>`.

## Tests

None yet — there is no test suite in this repo.
