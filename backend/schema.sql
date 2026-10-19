PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL,
 access_method TEXT NOT NULL, is_synthetic INTEGER NOT NULL DEFAULT 0,
 imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, reporting_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS observations (
 id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id), period TEXT NOT NULL,
 state TEXT NOT NULL, district TEXT NOT NULL, sector TEXT NOT NULL,
 occupation_code TEXT NOT NULL, occupation_title TEXT NOT NULL,
 demand_count INTEGER NOT NULL CHECK(demand_count >= 0), training_seats INTEGER NOT NULL CHECK(training_seats >= 0),
 quality_note TEXT NOT NULL DEFAULT '', UNIQUE(source_id,period,state,district,occupation_code)
);
CREATE INDEX IF NOT EXISTS idx_obs_period ON observations(period);
CREATE TABLE IF NOT EXISTS scenarios (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, inputs_json TEXT NOT NULL,
 result_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
