# SkillSight: AI-enabled Labour Market Intelligence System

**Smart India Hackathon 2026 · PS 26246 · Ministry of Skill Development & Entrepreneurship**

SkillSight fuses fragmented labour-market signals into one demand index and forecasts it 18 months ahead, with calibrated uncertainty. It then compares that forecast with migration-aware training supply for every district and trade. Beyond measuring gaps, it tells planners what to do next:
- next-cycle seat targets
- bridge courses that move surplus trainees into shortage trades
- curriculum revisions
- where to add training capacity
- an auto-drafted District Skill Development Plan

The system is multilingual and accessible, and has an API.

> **Demo data warning.** The bundled data is a deterministic *synthetic* universe shaped like NCS, EPFO, job-portal, e-Shram, PLFS and Skill India records, covering 4 states, 170 real districts, 24 trades and 36 months. It is not official statistics and is not connected to any government system. Because the simulation has a known ground truth, the methods are validated against it.

## What it does (problem-statement mapping)

| Expected outcome | SkillSight |
|---|---|
| Aggregate and normalise demand signals | LGD geo harmonisation, AI NCO-2015 auto-coder (TF-IDF + Gemini fallback), MinHash de-duplication with ghost-posting detection, benchmark calibration, and a **Unified Labour Demand Index** with self-learning source weights (triple collocation) |
| Cross-reference training capacity | Centre × QP × cycle seats, completion, certification, placement and wages, with **migration-aware** supply (out-flows and in-flows between districts) and absorbable e-Shram job-seekers |
| Forward-looking gap forecasts, updated periodically | Ensemble forecast (seasonal growth + damped Holt + global gradient boosting with an **announced-investment leading indicator**), conformal P10–P90 bands, hierarchical reconciliation, and refreshes every 24 h or on demand |
| Rank trades and geographies by severity | Five gap classes, a 0–100 severity score (magnitude, persistence, acceleration, wage signal, trust), and rankings by state, district, trade and sector |
| Early-warning flags | **Probabilistic** flags with the quarter they are expected in and driver attribution, plus an acknowledge/assign workflow, WhatsApp/email/SMS digests and webhooks |
| Interactive dashboard, national → district | Choropleth of India's 726 districts with drill-down from all pilot states to one state to one district, trade explorer, fan charts and a forecast accountability ledger |
| API and export layer | Versioned REST API with OpenAPI docs, read-only API keys, CSV/XLSX/JSON exports, and an **XLSX scheme target sheet** |
| Multilingual, accessible | English, हिन्दी, ಕನ್ನಡ, मराठी, ଓଡ଼ିଆ; light/dark/high-contrast themes; text size; keyboard navigation; table view for every chart; read-aloud; colour-independent status glyphs |

### Distinctive features
1. **Next-cycle Target Planner.** A MILP (HiGHS) sets integer seats for every district × trade. It minimises shortage and excess within budget, centre capacity and change limits, keeps the women-friendly seat share, and never cuts seats in aspirational districts. Odisha solves in about 0.3 s.
2. **Investment what-if simulator.** Describe a project (for example, a 2 GW solar park in Kalahandi). The model is re-run with it and shows which trades tip into shortage, how many extra seats are needed and what they cost, before hiring starts.
3. **Pivot Pathways.** Bridge courses from oversupplied trades to adjacent shortage trades, based on QP skill overlap (for example, Data Entry → Data Annotator, Electrician → Solar PV). They could redirect about 1.1 lakh.
4. **Curriculum Drift Radar.** Skills in job posts are compared with each NSQF QP to give a freshness score, missing skills and stale modules. Example: *EV battery repair QP is 39% fresh; add thermal management, high-voltage safety and OBD/CAN diagnostics.*
5. **Migration & capacity.** Corridor flows (for example, Ganjam → Bengaluru) and centre siting: where to sanction new capacity versus repurpose surplus seats.
6. **Disha copilot.** Ask in any of the five languages. Gemini function calling answers from the computed tables, with an offline engine when no API key is set.
7. **District Skill Development Plan.** One click produces a print-ready plan per district, with a narrative grounded in computed figures, in any of the five languages.
8. **Trust built in.** A data-trust score per cell widens forecast intervals. The validation metrics and the accountability ledger are shown in the product itself.

### Validation (latest run)

| Check | Result |
|---|---|
| Demand index error vs. ground truth | **10.8%** monthly / 8.2% quarterly (best single source 14.1%) |
| Forecast hold-out WAPE | **13.3%** (prototype linear trend 16.2%) |
| P10–P90 interval coverage | ~73% (nominal 80%) |
| Reconciliation incoherence | 0 |
| NCO auto-coding accuracy | 98.2% on held-out postings (97% auto-coded, the rest sent to review) |
| Duplicate postings removed | ~24% |

## Stack
- **Backend:** Python 3.11+, FastAPI, SQLite, NumPy/pandas, scikit-learn, SciPy (HiGHS MILP), rapidfuzz, openpyxl, Google Gen AI SDK (Gemini)
- **Frontend:** React 19, Vite 8, Tailwind CSS 4, Recharts, d3-geo, react-i18next
- **Auth:** optional Firebase sign-in; API keys for machine clients

See `docs/ARCHITECTURE.md`, `docs/METHODOLOGY.md` (all formulas) and `docs/DATA_DICTIONARY.md`.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate        # Windows: py -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend && npm install && npm run dev:full            # API on :8000, UI on :5173
```

Open http://127.0.0.1:5173.
- **First start:** generates the synthetic database (~5 s) and runs the full pipeline (~25 s).
- **Later starts:** serve stored results immediately and warm the model in the background.
- **Production build:** run `npm run build`; FastAPI then serves the UI at http://127.0.0.1:8000. API docs are at `/docs`.

Optional environment variables:

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Google Gemini key (from Google AI Studio). Enables Gemini for the copilot, DSDP narratives and hard NCO titles (default model `gemini-3.8-flash`; override with `SKILLSIGHT_GEMINI_MODEL`). Without it, everything works offline. `GOOGLE_API_KEY` is also accepted. |
| `SKILLSIGHT_REFRESH_HOURS` | Scheduled refresh interval (default 24; 0 disables) |
| `SKILLSIGHT_DB` | Database path (default `data/skillsight.db`) |
| `FIREBASE_PROJECT_ID` + `frontend/.env.local` `VITE_FIREBASE_*` | Turn on sign-in. Grant planner rights with `python -m backend.set_firebase_role <UID> planner`. |

To regenerate the demo data, run `python -m backend.synth.generate --reset`. It refuses if imported (non-synthetic) sources exist; delete `data/skillsight.db` in that case.

## Tests

```bash
python -m pytest -q          # 14 tests, ~50 s
cd frontend && npm run build
```

The tests cover:
- generator determinism and reset safety
- the fused index beating every single source
- the ensemble beating the legacy baseline
- hierarchy coherence and interval coverage
- detection of the planted storylines (Pune EV-battery shortage, data-entry saturation, the Koraput hospital early warning)
- MILP constraints (budget, change limits, women share, aspirational districts, infeasibility)
- XLSX target sheet, what-if, pathways, curriculum, siting
- alert workflow, offline copilot, Gemini function-calling loop (mocked), NCO classifier
- import harmonisation, exports, Hindi DSDP, API keys

## 7-minute demo script
1. **Command centre.** The KPIs show 30.6 lakh forecast openings against 34.1 lakh supply, but 6.4 lakh unmet: the problem is mismatch, not volume. On the map, red marks shortage and blue marks surplus. Point out the early-warning feed with Koraput health trades flagged about 3 quarters ahead of the new medical college.
2. **Geo drill-down.** Go from all pilot states to Odisha to Ganjam. Construction is oversupplied locally, but 15% of certified masons migrate to Khordha, Bengaluru and Mumbai. Open a trade to see its drivers and quarterly outlook, then open the **DSDP** in Hindi.
3. **Trade explorer.** EV Battery System Repair Technician: show the fan chart and the orange accountability line (last year's forecast against what happened), the backtest table, and the curriculum radar (*QP 42% fresh*).
4. **What-if.** "2 GW solar park in Kalahandi" yields 4 new construction-trade shortages, 4,695 extra seats and ₹6.5 cr, months before hiring begins.
5. **Target planner.** Odisha: 71% of unmet demand closed and 70% of excess removed at about ₹12 cr less spend, with women's share and aspirational districts protected. Download the XLSX target sheet.
6. **Skills.** Pivot pathways (Data Entry → Data Annotator bridge), then curriculum freshness.
7. **Disha.** Ask "ओडिशा में किन ट्रेडों में कमी है?", then switch the UI to Odia or Kannada, turn on high contrast and use read-aloud.
8. **Data hub / Methodology.** Source fusion weights, NCO auto-coder playground, CSV import with harmonisation (Bangalore → Bengaluru Urban), and the validation table.

## Limits
- District × trade detail is synthetic; state sizes are anchored to official EPFO shares, and official EPFO/PLFS figures are shown alongside. Trade codes are verified against NQR where possible (a few roles have only a closest QP, or no NCO code; each is flagged in the app).
- Supply assumes in-cycle certification and a stable migration matrix.
- Investment staffing shares are sector-level assumptions.
- SQLite is the evaluation store; production would use PostgreSQL/PostGIS and data-sharing connectors.
- All recommendations need planner review.
