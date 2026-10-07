# group-project-1

A small fullstack demo: a React frontend, a FastAPI backend, and PostgreSQL.

- **Frontend** — React + Vite dev server (`frontend/`), served on port 3000.
- **Backend** — FastAPI + SQLAlchemy (`backend/`), served on port 8000 inside the
  compose network.
- **Database** — PostgreSQL 16.

The browser only ever talks to port 3000; Vite proxies `/api/*` to the backend,
so there is a single origin and no CORS setup.

## Run it (development)

The sandbox environment is defined in `docker-compose.base44.yml`:

```bash
docker compose -f docker-compose.base44.yml up -d --build
```

Then open the preview (host port 3000). The stack runs from the cloned source
with live reload, so edits to `backend/` and `frontend/` apply without a rebuild.

Services: `db` (Postgres), `migrate` (one-shot table create + seed), `api`
(FastAPI), `web` (Vite dev server).

## API

- `GET /api/items` — list items
- `POST /api/items` — create an item (`{ "title", "description" }`)
- `DELETE /api/items/{id}` — delete an item

Interactive docs are available at `/api/docs` when running locally.
