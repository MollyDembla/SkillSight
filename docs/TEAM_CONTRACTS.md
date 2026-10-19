# Team contracts

Ownership for a six-person SIH team. Interfaces between areas are the database tables in `backend/schema.sql` and the `/api/v1` routes.

- **Data engineering** — `backend/synth/`, `backend/pipeline/{nco_coder,dedup}.py`, `backend/resolve.py`, `/api/v1/import`. Owns source registry, harmonisation, provenance and data tests.
- **Demand & forecasting** — `backend/pipeline/uldi.py`, `backend/models/{forecast,reconcile}.py`. Owns the demand index, ensemble, intervals and validation metrics.
- **Gap & decision models** — `backend/models/{gap,optimizer,insights}.py`. Owns supply model, severity, alerts, MILP, pathways, curriculum, siting, what-if.
- **Backend & AI integration** — `backend/api/`, `backend/services.py`, `backend/llm.py`, `backend/app.py`. Owns API contracts, exports, DSDP report, copilot, auth.
- **Frontend & accessibility** — `frontend/`. Owns pages, map, charts, i18n (5 languages), themes and keyboard/screen-reader support.
- **Policy, demo & quality** — `docs/`, README demo script, pitch deck, limitation language, end-to-end checks.

Definition of done: working API + UI path, provenance and limitations stated, errors validated, relevant tests added, `python -m pytest -q` and `npm run build` pass. Coordinate before changing response schemas.
