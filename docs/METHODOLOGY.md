# Methodology

SkillSight turns fragmented labour-market signals into one demand index, forecasts it, compares it with migration-aware training supply, and converts the gap into decisions. All steps run in `backend/pipeline/run.py` on startup, on demand and on a schedule (`SKILLSIGHT_REFRESH_HOURS`, default 24 h).

> **Data status.** District × trade × month detail is a deterministic synthetic universe (`backend/synth/generate.py`) shaped like the real sources: 4 states, 170 real districts (Census/LGD codes), 24 trades, 36 months (Oct 2023 – Sep 2026). It is tied to real data in three ways:
> 1. **Trade codes** are checked against the National Qualifications Register and Sector Skill Council QP lists. Each trade records its NCO and QP verification status and source.
> 2. **State sizes are anchored to official EPFO net-payroll shares.** The generator rescales each state so its simulated formal hiring matches EPFO's official shares, weighted by each sector's formal share.
> 3. **Official EPFO and PLFS figures** (`backend/data/official_stats.csv`, one source URL per value) are shown alongside the index.
>
> Because the simulation has a known ground truth, the methods can be validated against it — something real data never allows. The state-share comparison agrees by construction and is *not* a validation.

## 1. Sources and harmonisation

| Source (simulated) | Grain | Use |
|---|---|---|
| Online job portals (aggregate feed) | district × NCO × month | demand signal (urban-biased coverage, cross-posting duplicates) |
| National Career Service vacancies | district × NCO × month | demand signal (1-month publication lag) |
| EPFO new payroll subscribers | district × sector × month | demand signal (formal hiring; 2-month lag) |
| Annual establishment hiring benchmark | state × sector × FY | anchor for source coverage |
| Raw job postings (text, 12 months) | posting | NCO coding, de-duplication, skill extraction |
| Investment pipeline | project | leading indicator for forecasts |
| e-Shram registrations | district × NCO × month | job-seeker pool (supply) |
| Skill India Digital Hub records | centre × QP × FY | seats, enrolment, certification, placement, wages |
| Migration corridors | district → district × sector | supply redistribution |
| PLFS | state × quarter | context |

* **Geography** — free-text district names are matched to LGD codes with `rapidfuzz` plus an alias table (Bangalore → Bengaluru Urban, Noida → Gautam Buddha Nagar, Bhubaneswar → Khordha …). The CSV import rejects any row it cannot resolve.
* **Occupation coding** — character 2–4-gram TF-IDF + multinomial logistic regression, trained on the NCO title dictionary and human-coded ("gold") postings. Confidence ≥ 0.55 → auto-coded; below → human review queue, or Google Gemini when an API key is configured (`/api/v1/nco/classify`).
* **De-duplication** — MinHash (64 permutations) over word 3-shingles with LSH banding (16 × 4); candidate pairs are confirmed at Jaccard ≥ 0.6, same district, posted ≤ 14 days apart, then clustered with union-find. The measured posts-per-vacancy ratio per sector deflates the portal feed. Listings re-posted by the same employer in ≥ 3 distinct months are flagged as *ghost postings* and excluded from skill analysis.

## 2. Unified Labour Demand Index (ULDI)

For source *s*, district *d*, trade *t*, month *m*:

1. **Alignment.** Portal counts ÷ duplication factor; NCS shifted back one month; EPFO sector totals apportioned to trades by the district's trailing-12-month portal/NCS trade mix (state mix when thin).
2. **Benchmark coverage.** For each state × sector × fiscal year,
   `cov_s = Σ x_s / (B_state,sector,FY × f_present)`, where `f_present` is the share of the EPFO-implied frame that source *s* actually covers. Estimate `x̂_s = x_s / cov_s`.
3. **Small-area bias correction.** Portal and NCS reach differ between urban and rural districts. Each is cross-calibrated to EPFO, which has complete coverage, per district × sector, with empirical-Bayes shrinkage: `k = n/(n+200)`, `factor = k·ratio + (1−k)`.
4. **Precision weights.**
   * The structural error variance of each source comes from **triple collocation**, which needs no ground truth: `σ²_a = ½(Var(a−b) + Var(a−c) − Var(b−c))`, computed on relative deviations in well-populated cells, minus the mean sampling variance.
   * Per-cell **Poisson sampling variance** `1/count` adds to it, and the result is multiplied by publication freshness (portal 1.0, NCS 0.92, EPFO 0.85).
   * `w_s,cell = fresh_s / (σ²_s + 1/count_s,cell)`
   * `ULDI_cell = Σ_s w x̂_s / Σ_s w` over the sources present in that cell.
   * The weights are re-estimated on every refresh.
5. **Index.** `DemandIndex = 100 × ULDI / mean(ULDI over Oct 2023 – Sep 2024)`.
6. **Trust score** (0–1) per district × trade:
   `0.35·sources/3 + 0.30·agreement + 0.20·volume + 0.15·recency`,
   where agreement = 1 − CV across sources and volume = log-scaled openings.

**Validation (synthetic ground truth, district × trade × month):**

| Estimate | Monthly error (WAPE) |
|---|---|
| ULDI (fused) | 10.8% (8.2% quarterly) |
| Portal only | 14.1% |
| EPFO only | 14.2% |
| NCS only | 23.9% |

The fused index beats every individual source; this is enforced by a test.

## 3. Forecasting

Every district × trade series (4,080) is forecast for 18 months by three members:

* **Seasonal growth** — deseasonalised level × damped year-on-year growth × pooled seasonal index of the trade.
* **Damped Holt** — level/trend exponential smoothing (α 0.35, β 0.08, φ 0.9) on the deseasonalised series.
* **Global gradient boosting** — a single `HistGradientBoostingRegressor` across all series (M5-style), direct multi-horizon.
  * Target: `y_{t+h} / level_t`.
  * Features: horizon, calendar month, trade/sector (categorical), urbanisation, aspirational flag, log level, recent lag ratios, 6-month momentum, seasonal index, and the **announced-investment pipeline** at `t`, `t+h` and `t+h+2`.
  * Only projects announced on or before the forecast origin are used, so there is no look-ahead.

**Investment uplift** is a counterfactual: the GBM prediction minus the same prediction with the pipeline frozen at the origin. The two statistical members receive this uplift too, so announced projects move every member.

**Ensemble weights** are chosen per trade on the 3-member simplex (0.1 grid), minimising absolute error across rolling-origin backtests at Mar 2025, Sep 2025 and Mar 2026.

**Hold-out check:** weights fitted on the earlier origins and scored on Mar 2026 give 13.3% WAPE for the ensemble, against 16.2% for the prototype's original straight-line trend.

**Prediction intervals** use split conformal prediction: P10/P90 multipliers are the 10th/90th quantiles of actual ÷ forecast per sector × horizon bucket (1–3, 4–6, 7–12 months; √-time widening beyond 12). They are widened by `1 + 0.5·(1 − trust)`. Empirical coverage on a held-out origin is about 73% against a nominal 80%, and is reported on every run.

**Hierarchical reconciliation.** State and national forecasts come from damped Holt on the aggregated series plus summed uplift. They are combined with the district forecasts by weighted least squares (MinT-diagonal, W = forecast scale):

`b̃ = (S'W⁻¹S)⁻¹ S'W⁻¹ ŷ`

District + state + national figures are coherent to machine precision.

**Accountability ledger.** What each backtest origin predicted is stored next to what the index later measured, and shown on every trade chart.

## 4. Supply and gaps

For the current cycle (FY 2026-27 seats), the certified supply reaching district *d*'s labour market over the next 12 months is:

```
certified_d,t = seats × enrolment rate × (completion × certification yield, from FY23-26 history)
supply_d,t   = certified × (1 − out-migration share)
             + Σ_o certified_o,t × share(o→d, sector)
             + 0.12 × e-Shram registered job-seekers
```

* **Gap ratio:** `GR = (S − D) / D`, where D = P50 demand for the next 12 months (Oct 2026 – Sep 2027).
* **Classes:**

  | Class | Gap ratio |
  |---|---|
  | Acute shortage | ≤ −40% |
  | Shortage | ≤ −15% |
  | Balanced | between −15% and +20% |
  | Saturating | ≥ +20% |
  | Oversupplied | ≥ +60% |

* **Probabilities:** with `σ_D = (P90 − P10)/2.563`,
  * `P(shortage) = P(D > S/0.85)`
  * `P(surplus) = P(D < S/1.2)`
* **Quarterly outlook:** seasonally adjusted quarterly demand × 4 against annual supply gives the quarter in which a flag is expected (the lead time).
* **Severity (0–100):**
  `100 × [0.45·min(1,|GR|/0.8) + 0.15·persistence/3 + 0.15·acceleration + 0.10·wage signal + 0.15·trust]`
  * Persistence counts past fiscal-year cycles in the same class.
  * Acceleration is demand growth in the direction of the gap.
  * Wage signal: placement wages rising faster than 10% confirm a shortage; slower than 10% confirms a surplus.
  * Balanced cells are scaled by 0.35, and the score is down-weighted for very small cells.
* **Drivers** (each flag):
  * organic trend
  * investment hiring waves (net change)
  * change in training seats
  * net migration
  * absorbable job-seekers

## 5. Early-warning flags

| Kind | Rule |
|---|---|
| `acute_shortage` | GR ≤ −40%, P(shortage) ≥ 0.7, demand ≥ 60, severity ≥ 50 |
| `saturation` | GR ≥ +60%, P(surplus) ≥ 0.7, demand ≥ 60, severity ≥ 50 |
| `emerging_shortage` | next quarter not in shortage, but a later quarter has P(shortage) ≥ 0.6 (lead = that quarter) |
| `emerging_saturation` | symmetric |

Planner workflow status (open / acknowledged / assigned / actioned / dismissed) persists across refreshes. Digests (WhatsApp / email / SMS) and webhooks push flags to state units.

## 6. Decision support

* **Target optimiser** (`models/optimizer.py`) — a MILP solved with HiGHS via `scipy.optimize.milp`, deciding integer seats `x` for FY 2027-28.
  * Objective: minimise `Σ w_short·u + w_surplus·v + ε·cost·x`, where `u ≥ D − (a·x + b)` and `v ≥ a·x + b − 1.1·D`. D is demand for Apr 2027 – Mar 2028 at P50 plus a chosen share of the P50–P90 band (risk appetite).
  * Supply terms: `a` = enrolment × yield × (1 − out-migration); `b` = in-migration + seekers.
  * Constraints:
    * budget
    * district centre capacity (+15%)
    * per-course change of ±50%, with up to +40 seats allowed for new courses
    * women-friendly seat share no lower than the current share
    * no cuts in aspirational districts
  * A whole state solves in under a second, and all 4,080 cells in about 1.5 s.
  * Output is an XLSX / CSV / JSON target sheet.
* **Pivot pathways** — skill overlap = |source-QP skills ∩ target-market skills| / |target-market skills|.
  * Feasible when overlap ≥ 0.25 and NSQF levels are within 1.
  * Bridge hours = target hours × (1 − overlap) × 0.6.
  * Absorbable = min(surplus, shortage) × min(1, 1.6 × overlap).
* **Curriculum drift radar** — skills are extracted from posting text (taxonomy match; Gemini for unseen phrasing when configured).
  * Freshness = share of skill mentions in recent postings that the QP covers.
  * Missing skills: absent from the QP and in ≥ 15% of postings. Stale QP skills: in < 5% of postings.
* **What-if simulator** — injects a hypothetical project into the pipeline features and re-predicts with the fitted GBM. The announced hiring itself serves as a floor on the uplift, since trees cannot extrapolate beyond project sizes they have seen. The gap engine is then re-run.
* **Centre siting** — seats needed for shortage trades, minus spare centre capacity, minus seats repurposable from oversupplied trades, gives the net new capacity. The priority score weights aspirational districts and distance to the nearest centre.
* **AI copilot** — Gemini function calling over the same query layer (gaps, rollups, alerts, forecasts, pathways, curriculum, what-if). Every number comes from a tool result. An offline intent engine answers without an API key.

## 7. Limitations

* The data is synthetic. Real deployment needs data-sharing agreements (NCS, EPFO, SIDH, e-Shram), verified NCO↔QP concordances and an annual hiring benchmark.
* Supply assumes certification within the cycle and a stable migration matrix; placement-outcome feedback should recalibrate both.
* The investment-to-jobs staffing shares are sector-level assumptions and should be replaced with SSC staffing norms.
* Recommendations are advisory and require planner review.
