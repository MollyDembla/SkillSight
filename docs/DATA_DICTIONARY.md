# Data dictionary

All tables are defined in `backend/schema.sql`. Bundled rows are synthetic (`sources.is_synthetic = 1`).

## Reference

| Table | Key fields | Notes |
|---|---|---|
| `districts` | `lgd`, `state`, `district`, `lat`, `lon`, `urban`, `pop_weight`, `aspirational` | 170 pilot districts; codes from Census 2011 boundary data; aspirational = NITI Aayog list |
| `trades` | `code` (verified NCO-2015 code, or an internal `LMIS-` id when NCO has none), `title`, `sector`, `qp_code`, `nsqf_level`, `hours`, `cost_per_seat` (₹), `women_share`, `entry_wage` (₹/month), `emerging`, `nco_code`, `nco_status`, `qp_status`, `qp_title`, `source_url`, `code_note` | Codes checked against nqr.gov.in and Sector Skill Council QP lists; status and source per trade |
| `qp_skills` | `trade_code`, `skill` | Skills listed in the current QP |

## Sources and raw data

| Table | Key fields | Notes |
|---|---|---|
| `sources` | `key`, `name`, `source_type`, `access_method`, `grain`, `lag_months`, `side`, `is_synthetic` | Provenance registry; imports get `key = import-<id>` |
| `signals` | `source_id`, `period` (YYYY-MM), `lgd`, `sector`, `trade_code` ('' when sector-level), `value` | Aggregate counts |
| `benchmarks` | `state`, `sector`, `fy`, `hires` | Annual anchor for coverage |
| `plfs` | `state`, `quarter`, `youth_ur`, `lfpr` | Legacy, now empty: replaced by official PLFS figures in `official_stats` |
| `postings` | `portal`, `posted_on`, `lgd`, `employer`, `raw_title`, `description`, `salary`, `gold_code`, `nco_code`, `nco_conf`, `coder`, `cluster_id`, `ghost` | `eval_code` holds simulation truth for evaluation only |
| `investments` | `name`, `lgd`, `sector`, `capex_cr`, `jobs_ops`, `jobs_build`, `announced`, `build_start`, `ops_start`, `ramp_months` | Leading indicator |
| `centres` | `lgd`, `name`, `scheme`, `capacity`, `lat`, `lon` | Training centres |
| `supply` | `centre_id`, `trade_code`, `fy`, `seats`, `enrolled`, `completed`, `certified`, `placed`, `avg_wage`, `women` | FY 2026-27 is in progress (no completions yet) |
| `migration` | `origin_lgd`, `dest_lgd`, `sector`, `share` | Share of certified workers who move |
| `official_stats` | `source` (EPFO / PLFS), `period`, `state`, `indicator`, `value`, `definition`, `url` | Real published figures, one source URL per value (`backend/data/official_stats.csv`) |
| `synthetic_truth` | `period`, `lgd`, `trade_code`, `openings` | Simulation ground truth; used only to validate |

## Pipeline outputs

| Table | Meaning |
|---|---|
| `uldi` | Fused openings estimate, demand index (base Oct 2023–Sep 2024 = 100), sources present, cell trust |
| `source_weights` | Learned weight, structural error variance and coverage per sector × source |
| `forecasts` | `node` (LGD code, `ST:<state>` or `IN`) × trade × month: P10 / P50 / P90 and investment uplift |
| `backtests` | WAPE and ensemble weight per trade × model |
| `ledger` | Past forecasts vs. later measured index at state / national level |
| `gaps` | Per district × trade, next 12 months: demand P10/P50/P90; supply components (local certified, outflow, inflow, seekers); gap, gap ratio, status, severity; P(shortage), P(surplus), lead quarter, trust; persistence, wage growth, placement rate; drivers, quarterly outlook and history (JSON) |
| `alerts` | Early-warning flags with workflow status (`open`, `acknowledged`, `assigned`, `actioned`, `dismissed`) |
| `pipeline_runs` | Run log with full validation summary JSON |
| `scenarios` | Saved optimiser runs (inputs + result) |
| `api_keys`, `webhooks` | Integration access |

## Units and conventions

* Demand is **openings per month** at district × trade level; forecasts are monthly; gaps cover 12 months.
* Gap ratio = (supply − demand) / demand. Negative means shortage.
* Indian digit grouping in the UI (lakh = 1,00,000; crore = 1,00,00,000).
* Fiscal year runs April–March (`2026-27`).
