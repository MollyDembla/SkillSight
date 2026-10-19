PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Reference taxonomy
CREATE TABLE IF NOT EXISTS districts (
 lgd TEXT PRIMARY KEY, state TEXT NOT NULL, district TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
 urban REAL NOT NULL, pop_weight REAL NOT NULL, aspirational INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trades (
 code TEXT PRIMARY KEY, title TEXT NOT NULL, sector TEXT NOT NULL, sector_name TEXT NOT NULL, qp_code TEXT NOT NULL,
 nsqf_level INTEGER NOT NULL, hours INTEGER NOT NULL, cost_per_seat INTEGER NOT NULL, women_share REAL NOT NULL,
 entry_wage INTEGER NOT NULL, emerging INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS qp_skills (
 trade_code TEXT NOT NULL REFERENCES trades(code), skill TEXT NOT NULL, PRIMARY KEY(trade_code, skill)
);

-- Source registry and raw signals (provenance kept for every row)
CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY, key TEXT UNIQUE, name TEXT NOT NULL, source_type TEXT NOT NULL,
 access_method TEXT NOT NULL, is_synthetic INTEGER NOT NULL DEFAULT 0, grain TEXT NOT NULL DEFAULT '',
 lag_months INTEGER NOT NULL DEFAULT 0, side TEXT NOT NULL DEFAULT 'demand',
 imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reporting_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS signals (
 source_id INTEGER NOT NULL REFERENCES sources(id), period TEXT NOT NULL, lgd TEXT NOT NULL REFERENCES districts(lgd),
 sector TEXT NOT NULL, trade_code TEXT NOT NULL DEFAULT '', value REAL NOT NULL CHECK(value >= 0),
 PRIMARY KEY(source_id, period, lgd, sector, trade_code)
);
CREATE INDEX IF NOT EXISTS idx_signals_trade ON signals(trade_code, lgd);
CREATE TABLE IF NOT EXISTS benchmarks (
 state TEXT NOT NULL, sector TEXT NOT NULL, fy TEXT NOT NULL, hires REAL NOT NULL, PRIMARY KEY(state, sector, fy)
);
CREATE TABLE IF NOT EXISTS plfs (
 state TEXT NOT NULL, quarter TEXT NOT NULL, youth_ur REAL NOT NULL, lfpr REAL NOT NULL, PRIMARY KEY(state, quarter)
);
CREATE TABLE IF NOT EXISTS postings (
 id INTEGER PRIMARY KEY, portal TEXT NOT NULL, posted_on TEXT NOT NULL, lgd TEXT NOT NULL REFERENCES districts(lgd),
 employer TEXT NOT NULL, raw_title TEXT NOT NULL, description TEXT NOT NULL, salary INTEGER,
 gold_code TEXT, eval_code TEXT, nco_code TEXT, nco_conf REAL, coder TEXT, cluster_id INTEGER, ghost INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS investments (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, lgd TEXT NOT NULL REFERENCES districts(lgd), sector TEXT NOT NULL,
 capex_cr REAL NOT NULL, jobs_ops INTEGER NOT NULL, jobs_build INTEGER NOT NULL, announced TEXT NOT NULL,
 build_start TEXT NOT NULL, ops_start TEXT NOT NULL, ramp_months INTEGER NOT NULL, hypothetical INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS centres (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, lgd TEXT NOT NULL REFERENCES districts(lgd), lat REAL NOT NULL, lon REAL NOT NULL,
 scheme TEXT NOT NULL, capacity INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS supply (
 centre_id INTEGER NOT NULL REFERENCES centres(id), trade_code TEXT NOT NULL REFERENCES trades(code), fy TEXT NOT NULL,
 seats INTEGER NOT NULL, enrolled INTEGER NOT NULL, completed INTEGER NOT NULL, certified INTEGER NOT NULL,
 placed INTEGER NOT NULL, avg_wage INTEGER NOT NULL, women INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(centre_id, trade_code, fy)
);
CREATE TABLE IF NOT EXISTS migration (
 origin_lgd TEXT NOT NULL, dest_lgd TEXT NOT NULL, sector TEXT NOT NULL, share REAL NOT NULL,
 PRIMARY KEY(origin_lgd, dest_lgd, sector)
);
-- Simulation ground truth: exists only because the data is synthetic; used for validation, never by the models.
CREATE TABLE IF NOT EXISTS synthetic_truth (
 period TEXT NOT NULL, lgd TEXT NOT NULL, trade_code TEXT NOT NULL, openings REAL NOT NULL, PRIMARY KEY(period, lgd, trade_code)
);

-- Pipeline outputs
CREATE TABLE IF NOT EXISTS pipeline_runs (
 id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, trigger TEXT NOT NULL,
 summary_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS uldi (
 period TEXT NOT NULL, lgd TEXT NOT NULL, trade_code TEXT NOT NULL, openings REAL NOT NULL, demand_index REAL NOT NULL,
 n_sources INTEGER NOT NULL, trust REAL NOT NULL, PRIMARY KEY(period, lgd, trade_code)
);
CREATE TABLE IF NOT EXISTS source_weights (
 sector TEXT NOT NULL, source_key TEXT NOT NULL, weight REAL NOT NULL, error_var REAL NOT NULL, coverage REAL NOT NULL,
 PRIMARY KEY(sector, source_key)
);
CREATE TABLE IF NOT EXISTS forecasts (
 node TEXT NOT NULL, trade_code TEXT NOT NULL, period TEXT NOT NULL, p10 REAL NOT NULL, p50 REAL NOT NULL, p90 REAL NOT NULL,
 invest_effect REAL NOT NULL DEFAULT 0, PRIMARY KEY(node, trade_code, period)
);
CREATE TABLE IF NOT EXISTS backtests (
 trade_code TEXT NOT NULL, model TEXT NOT NULL, wape REAL NOT NULL, weight REAL NOT NULL, PRIMARY KEY(trade_code, model)
);
CREATE TABLE IF NOT EXISTS gaps (
 lgd TEXT NOT NULL, trade_code TEXT NOT NULL, demand_p10 REAL NOT NULL, demand_p50 REAL NOT NULL, demand_p90 REAL NOT NULL,
 demand_last12 REAL NOT NULL, supply REAL NOT NULL, local_certified REAL NOT NULL, outflow REAL NOT NULL, inflow REAL NOT NULL,
 seekers REAL NOT NULL, seats REAL NOT NULL, gap REAL NOT NULL, gap_ratio REAL NOT NULL, status TEXT NOT NULL,
 severity REAL NOT NULL, p_shortage REAL NOT NULL, p_surplus REAL NOT NULL, lead_quarter INTEGER, trust REAL NOT NULL,
 persistence INTEGER NOT NULL, wage_growth REAL NOT NULL, placement_rate REAL NOT NULL, invest_effect REAL NOT NULL,
 drivers_json TEXT NOT NULL, quarters_json TEXT NOT NULL, history_json TEXT NOT NULL, PRIMARY KEY(lgd, trade_code)
);
CREATE TABLE IF NOT EXISTS alerts (
 id INTEGER PRIMARY KEY, lgd TEXT NOT NULL, trade_code TEXT NOT NULL, kind TEXT NOT NULL, probability REAL NOT NULL,
 lead_quarter INTEGER, severity REAL NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 assignee TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 active INTEGER NOT NULL DEFAULT 1, UNIQUE(lgd, trade_code, kind)
);
CREATE TABLE IF NOT EXISTS scenarios (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'targets', inputs_json TEXT NOT NULL,
 result_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS api_keys (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, key_hash TEXT NOT NULL UNIQUE, prefix TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS webhooks (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL, min_severity REAL NOT NULL DEFAULT 60, state TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ledger (
 node TEXT NOT NULL, trade_code TEXT NOT NULL, origin TEXT NOT NULL, period TEXT NOT NULL, forecast REAL NOT NULL,
 actual REAL NOT NULL, PRIMARY KEY(node, trade_code, origin, period)
);
