# Team contracts

- **Data engineering:** own source registry, CSV validation, de-duplication, provenance, and import tests (`backend/import` API and `sources`/`observations` schema).
- **Analytics:** own transparent measures, trend baseline and alerts (`backend/analytics.py` and forecast APIs).
- **Optimization:** own constraints, objective, feasibility and reproducibility (`/api/allocations/*`).
- **Backend integration:** own FastAPI contracts, SQLite persistence, startup and API errors.
- **Frontend:** own the browser SPA, accessible states, filters and API wiring (`frontend/`).
- **Policy/demo and quality:** own documentation, limitation language, walkthrough and scenario review.

Shared observation fields and meanings are defined in `DATA_DICTIONARY.md`; API routes and flow are in `ARCHITECTURE.md`. Keep the prototype aggregate-only. Changes to response schemas should be coordinated before merging. Use the documented local setup in `README.md`; Python tests run with `python -m pytest -q`. Integrate small changes against the same local API. Definition of done: the feature has a working API/UI path, records provenance and limitations, validates errors, has relevant business-logic tests, and the documented commands succeed. No contributors or branch automation are preconfigured in this empty repository.
