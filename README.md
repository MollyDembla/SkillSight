# SkillSight — Labour Market Intelligence

SkillSight is a local-first decision-support prototype for exploring labour demand and training indicators, reviewing transparent forecasts and alerts, and testing constrained seat allocations. Firebase authentication is optional for the local synthetic-data demo and becomes required when `FIREBASE_PROJECT_ID` is configured on the backend.

**Demo data warning:** The included records are deterministic synthetic demonstration data, not official government statistics and not connected to MSDE, NCS, PLFS, e-Shram, or any live vacancy feed. The current schema has demand observations and training capacity only; it does not contain comparable workforce supply, placements, or certifications. Therefore the application does not claim a measured shortage/oversupply or workforce gap.

## Stack and structure

- Python 3.11+, FastAPI, Pydantic, SQLite, pandas, NumPy
- React 19, Vite 8, Tailwind CSS 4 frontend; FastAPI backend
- CSV import with validation and transaction rollback; JSON API and CSV exports
- SQLite stores source provenance, observations, and saved scenarios

`backend/` holds API, schema, analytics and seed data. `frontend/src/` holds React views; Vite builds the Tailwind CSS application to `frontend/dist/`. `docs/` documents data definitions, methods, architecture, and team interfaces.

## Run locally

In PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Install frontend packages once:

```powershell
cd frontend
npm install
```

Start both services together from `frontend`:

```powershell
npm run dev:full
```

The script starts FastAPI on port 8000 and Vite on port 5173. Open http://127.0.0.1:5173. It uses the project `.venv` Python when present, or `python` on `PATH`. To run the services separately, start `python -m uvicorn backend.app:app --reload` from the repository root, then `npm run dev` from `frontend`.

Vite proxies API requests to FastAPI. To serve the production frontend through FastAPI, run `npm run build` from `frontend`, then start/restart the API and open http://127.0.0.1:8000. API docs are at `/docs`; health is at `/api/health`. The app initializes SQLite and seeds the bundled demo records on first API start; its database path defaults to `data/skillsight.db` and can be set with `SKILLSIGHT_DB`.

## Firebase authentication

The supplied Firebase web app settings are stored locally in the ignored file `frontend/.env.local`. The Firebase Web API key is client configuration, not a password or service-account secret. Analytics is not initialized because it is not needed for authentication.

1. In Firebase Console, enable **Authentication ? Email/Password**. Confirm `localhost` and `127.0.0.1` are in Authentication's authorized domains, then create a test user. Public self-registration is not offered.
2. From the repository root, set the backend project ID and run both services:

   ```powershell
   $env:FIREBASE_PROJECT_ID = "skillsight-4486e"
   cd frontend
   npm run dev:full
   ```

   Open http://127.0.0.1:5173 and sign in. The backend checks ID token signatures against Google's public signing certificates and validates the configured Firebase project. It does not need a service-account file for login. `/api/health` remains public. Import and scenario-save operations require the Firebase custom claim `role` to be `planner` or `admin`; other signed-in accounts can use read-only features.
3. To grant planner access, provision a Firebase Admin SDK credential separately (Application Default Credentials or a protected service-account file), then assign a role by UID with `python -m backend.set_firebase_role USER_UID planner` (or `admin`). Never commit that credential. Have the user sign out and back in after a claim change.

Restrict the Firebase Web API key to the Firebase APIs in Google Cloud. The optional Admin SDK credential is sensitive and must stay outside the repository.

## CSV import

Upload UTF-8 CSV through **Data & quality**. Required columns: `period` (YYYY-MM), `state`, `district`, `sector`, `occupation_code`, `occupation_title`, `demand_count`, `training_seats`. Optional CSV column: `quality_note`. Source label, type, and access method are captured in the import form. Counts must be nonnegative integers. Every import records its source and ingest timestamp and is committed atomically. Unknown occupation codes are retained as supplied; no fabricated NCO mapping is applied. Files are limited to 5 MiB. No worker-level data is requested.

## Tests and verification

```powershell
python -m pytest tests -q -p no:cacheprovider
```

The backend tests cover deterministic seed/aggregation, input validation, forecast horizon and reproducibility, constrained allocation feasibility, infeasibility, Firebase middleware behavior, and API workflows. Verify the frontend production bundle with `cd frontend; npm run build`.

## Judging walkthrough

1. Review observed demand totals and training seats on Overview; check the synthetic-data banner.
2. Filter by state/sector, then open Occupations or Geography to inspect supported details.
3. Review the deterministic trend baseline and evidence-backed threshold alerts in Forecasts & alerts.
4. In Allocation, set budget and district capacity and calculate a feasible allocation; inspect constraints and save it.
5. Reload saved scenarios and download observation or scenario CSV from Reports.
6. Import a small CSV in Data & quality to demonstrate validation, provenance and refreshed results.

## Known limits

This is a prototype, not a certified or connected government system. Its map view is a geographic comparison table because no boundary dataset was supplied. Forecasts are linear-trend baselines with no accuracy score or confidence interval; short histories are marked insufficient. The allocator optimizes coverage of recorded demand proxy under user-entered cost/capacity, not real job placements or policy impact. Firebase authentication is available when configured, but production identity governance, audit approval workflows, Excel import, and production deployment are not implemented. Scenario saves are local prototype records and should receive human review.
