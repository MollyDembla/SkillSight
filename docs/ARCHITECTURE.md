# Architecture

A modular monolith: FastAPI (Python) owns ingestion, analytics and the API; React (Vite + Tailwind) is the planner UI. SQLite is the evaluation store; the schema is plain SQL so the PostgreSQL/PostGIS move is mechanical.

```
backend/
  catalog.py          reference taxonomy: pilot geography, 24 trades (NCO/QP), skills, staffing, investments
  db.py               connection, schema bootstrap, calendar (history / forecast / gap / cycle windows)
  synth/generate.py   deterministic synthetic universe (truth + per-source observations)
  pipeline/           nco_coder · dedup · uldi (fusion + trust) · run (orchestrator, in-memory model state)
  models/             forecast (ensemble, conformal) · reconcile (MinT) · gap (supply, classes, alerts)
                      optimizer (MILP) · insights (pathways, curriculum, siting, what-if)
  services.py         read-side query layer shared by API, exports, reports and copilot tools
  resolve.py          fuzzy geo / occupation harmonisation
  llm.py              Google Gemini copilot (function calling), DSDP narrative, NCO fallback; offline engine
  api/v1.py           REST router · exports.py (CSV/XLSX/JSON, target sheet) · report.py (DSDP HTML)
  app.py              app factory, Firebase / API-key auth, scheduler, static hosting
frontend/src/
  App.jsx             shell: navigation, filters, language, theme, text size, auth gate
  pages/*             Overview, GeoPage, Trades, Alerts, Planner, WhatIf, Mobility, Skills, DataHub, Reports, Methodology
  components/*        ui (cards, tables, badges), charts (recharts), IndiaMap (d3-geo), Copilot, Auth
  i18n.js             English, हिन्दी, ಕನ್ನಡ, मराठी, ଓଡ଼ିଆ
frontend/public/geo/  simplified district boundaries (726 districts; pilot states at higher resolution)
scripts/build_geo.py  rebuilds the boundary assets from the open GeoJSON source
```

## Data flow

1. The raw sources go into the `signals`, `postings`, `supply`, `centres`, `migration`, `investments` and `benchmarks` tables.
2. The refresh pipeline then runs in this order:
   1. NCO coding
   2. MinHash de-duplication
   3. ULDI fusion, written to the `uldi` and `source_weights` tables
   4. backtests (`backtests`, `ledger`)
   5. ensemble forecast with conformal intervals and reconciliation (`forecasts`)
   6. migration-aware gaps (`gaps`)
   7. early-warning upserts (`alerts`)
3. The read API, exports and reports serve from these tables.
4. Stateful decisions (optimiser, what-if, pathways, siting) use the fitted model state cached in memory by the last run. On restart, stored results are served at once while the model warms up in a background thread.

## API surface (`/api/v1`, OpenAPI at `/docs`)

| Area | Endpoints |
|---|---|
| Reference | `reference`, `centres`, `methodology/metrics` |
| Intelligence | `overview`, `map`, `gaps`, `rankings`, `districts/{lgd}`, `trades/{code}/series`, `mobility` |
| Early warning | `alerts` (GET/PATCH), `alerts/digest`, `webhooks` |
| Decision | `targets/optimize`, `targets/export`, `scenarios`, `simulate/investment`, `pathways`, `curriculum`, `siting` |
| AI | `copilot/chat`, `copilot/status`, `nco/classify` |
| Data | `sources`, `postings`, `quality`, `pipeline/runs`, `pipeline/run`, `import` |
| Export | `exports/{gaps,forecasts,alerts,rankings,uldi}.{csv,xlsx,json}`, `reports/dsdp/{lgd}?lang=` |
| Access | `api-keys` (create / list / revoke) |

## Security model

* Local demo mode: no authentication.
* Setting `FIREBASE_PROJECT_ID` makes every `/api/*` route except `/api/health` require one of:
  * a Firebase ID token, or
  * an `X-API-Key` header — machine access, read-only; only the SHA-256 hash of each key is stored.
* Mutating routes (import, scenarios, pipeline runs, keys, webhooks, alert workflow) need a Firebase custom `role` claim of `planner` or `admin`. Set it with `backend/set_firebase_role.py`.
* Only aggregate, non-personal data is stored.
* Gemini receives computed aggregates only, never raw records about individuals.

## Production path

* PostgreSQL + PostGIS (official LGD boundaries).
* A scheduled worker (Celery or Cloud Run jobs) for refreshes.
* Data-sharing connectors for NCS / EPFO / SIDH / e-Shram APIs.
* Object storage for raw postings.
* SSO via the state government identity provider.
* Hosting on NIC / MeghRaj, aligned with GIGW 3.0.
