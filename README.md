# group-project-1

A digital document signing and verification service: a React frontend, a FastAPI
backend, and PostgreSQL.

- **Frontend** — React + Vite dev server (`frontend/`), served on port 3000.
- **Backend** — FastAPI + SQLAlchemy (`backend/`), served on port 8000 inside the
  compose network.
- **Database** — PostgreSQL 16.
- **Document storage** — uploaded files are kept privately on a Docker volume
  (`uploads`, mounted at `/data/documents`). There is no public URL; files are
  only reachable through the API by signing token.

The browser only ever talks to port 3000; Vite proxies `/api/*` to the backend,
so there is a single origin and no CORS setup.

## How it works

1. **Upload** a document on the home page. The service stores it, computes its
   SHA-256 hash, and creates a unique **signing link** (`/sign/<token>`).
2. **Send the link** to the signer. Opening it shows the document for review and
   a form to sign with a name and email.
3. **Signing** records three layers, all bound to the document hash:
   - an *acknowledgement record* — signer name, email, timestamp, IP;
   - an *HMAC-SHA256 signature* keyed with the service's secret;
   - an *RSA (X.509) signature* verifiable by anyone holding the certificate.
4. **Verify** on the `/verify` page: upload a file and the service reports
   whether it matches a signed document, plus a pass/fail check for each layer.
   A changed file hashes differently and matches no signature.

The RSA keypair, self-signed certificate and HMAC secret are generated once by
the `migrate` service and stored in the `signing_keys` table, so signatures stay
verifiable across restarts.

## Run it (development)

The sandbox environment is defined in `docker-compose.base44.yml`:

```bash
docker compose -f docker-compose.base44.yml up -d --build
```

Then open the preview (host port 3000). The stack runs from the cloned source
with live reload, so edits to `backend/` and `frontend/` apply without a rebuild.

Services: `db` (Postgres), `migrate` (one-shot table create + key generation),
`api` (FastAPI), `web` (Vite dev server).

## API

- `GET /api/documents` — list documents with signature status
- `POST /api/documents` — upload a document (multipart `file`), returns its signing token
- `GET /api/documents/{token}` — document detail
- `GET /api/documents/{token}/download` — download the stored original
- `POST /api/documents/{token}/sign` — sign (`{ "name", "email" }`)
- `POST /api/verify` — verify an uploaded file (multipart `file`)

Interactive docs are available at `/api/docs` when running locally.
