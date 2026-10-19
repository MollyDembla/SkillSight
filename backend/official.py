"""Official published statistics (EPFO payroll, PLFS) used as real context and to anchor the synthetic universe.

Values live in backend/data/official_stats.csv - one row per published number, each with its source URL - so every
figure shown as "official" can be traced to the release it came from. Nothing in this file is estimated.
"""
from __future__ import annotations
import csv
from collections import defaultdict
from .catalog import DATA_DIR, PILOT_STATES

CSV_PATH = DATA_DIR / "official_stats.csv"
SOURCES = {
    "EPFO": ("EPFO payroll data (official)", "official_publication", "Ministry of Labour & Employment / PIB monthly payroll releases", "state x month"),
    "PLFS": ("Periodic Labour Force Survey (official)", "official_publication", "MoSPI PLFS annual reports and bulletins", "state x period"),
}


def read_csv() -> list[dict]:
    if not CSV_PATH.is_file():
        return []
    with CSV_PATH.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("value", "").strip()]
    for r in rows:
        r["value"] = float(r["value"])
    return rows


def load(c) -> int:
    """(Re)load the CSV into official_stats and register each official source with its provenance."""
    rows = read_csv()
    c.execute("DELETE FROM official_stats")
    c.executemany("INSERT OR REPLACE INTO official_stats VALUES(?,?,?,?,?,?,?)",
                  [(r["source"], r["period"], r["state"], r["indicator"], r["value"], r.get("definition", ""), r["url"]) for r in rows])
    for key, (name, stype, access, grain) in SOURCES.items():
        if any(r["source"] == key for r in rows) and not c.execute("SELECT 1 FROM sources WHERE key=?", (f"official-{key.lower()}",)).fetchone():
            c.execute("INSERT INTO sources(key,name,source_type,access_method,is_synthetic,grain,side,reporting_note) VALUES(?,?,?,?,0,?,'context',?)",
                      (f"official-{key.lower()}", name, stype, access, grain, "Real published figures; each value carries its source URL."))
    return len(rows)


def state_shares(indicator: str = "net_payroll_additions", source: str = "EPFO") -> dict[str, float] | None:
    """Average share of each pilot state in the combined pilot total, over all months where all 4 states are published."""
    by_period = defaultdict(dict)
    for r in read_csv():
        if r["source"] == source and r["indicator"] == indicator and r["state"] in PILOT_STATES:
            by_period[r["period"]][r["state"]] = r["value"]
    complete = [v for v in by_period.values() if len(v) == len(PILOT_STATES) and sum(v.values()) > 0]
    if not complete:
        return None
    shares = {s: sum(v[s] / sum(v.values()) for v in complete) / len(complete) for s in PILOT_STATES}
    return shares
