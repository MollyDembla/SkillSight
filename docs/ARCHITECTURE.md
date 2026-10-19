# Architecture

SkillSight uses a local-first modular monolith: FastAPI serves the JSON API; SQLite stores source registry, observations, and scenario snapshots. The React 19 client is built with Vite 8 and Tailwind CSS 4. During development Vite proxies `/api`, `/docs`, and `/static` to FastAPI at port 8000; `npm run dev:full` starts both services. In production, `npm run build` places static assets in `frontend/dist`; FastAPI serves the built app at `/` and `/assets`. `backend/analytics.py` contains pure deterministic forecasting and optimization functions. `backend/seed.py` creates a repeatable, fixed synthetic fixture.

Firebase Authentication is optional in local demo mode. Setting `FIREBASE_PROJECT_ID` enables backend ID-token verification for all `/api/*` endpoints except `/api/health`. The Firebase Admin SDK uses Application Default Credentials. Mutating CSV import and scenario-save operations require a Firebase custom `role` claim of `planner` or `admin`; other authenticated callers have viewer access. The Vite client requires matching `VITE_FIREBASE_*` values. No identity secrets are stored in the repository.

## Data flow

CSV upload → UTF-8/size/schema/date/count validation → duplicate check → single SQLite transaction → source provenance and observation rows → filtered aggregations → overview, geography, occupation, forecast and alert endpoints → client. Scenario inputs are validated by Pydantic, optimized against latest-period records, and saved with the computed result JSON.

## API surface

- `GET /api/health`, `/api/filters`, `/api/overview`
- `GET /api/occupations`, `/api/occupations/{code}`, `/api/geography`
- `GET /api/forecasts`, `/api/alerts`
- `POST /api/allocations/optimize`, `POST /api/scenarios`; `GET /api/scenarios[/{id}]`
- `GET /api/sources`, `POST /api/import`
- `GET /api/exports/observations.csv`, `/api/exports/scenarios.csv`

Interactive OpenAPI documentation is served at `/docs`.

## Boundaries

SQLite is a practical evaluation backend, not the production PostgreSQL/PostGIS target. There is no real geospatial boundary layer or multi-user concurrency guarantee. Firebase setup and role provisioning must be managed by the deploying organization. The database schema records only aggregate monthly occupation demand and training-seat capacity. A workforce supply measure is absent; the application keeps that metric and gap label unavailable.
