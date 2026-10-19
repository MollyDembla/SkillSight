"""SQLite connection helpers and period utilities shared by the pipeline and API."""
from __future__ import annotations
import os, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def db_path() -> Path:
    return Path(os.getenv("SKILLSIGHT_DB", ROOT / "data" / "skillsight.db"))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript((ROOT / "backend" / "schema.sql").read_text(encoding="utf-8"))
    return c


def rows(c: sqlite3.Connection, sql: str, args=()) -> list[dict]:
    return [dict(r) for r in c.execute(sql, args).fetchall()]


# Monthly calendar of the demonstration dataset.
FIRST_PERIOD = "2023-10"
N_MONTHS = 36
HORIZON = 18


def add_months(period: str, n: int) -> str:
    y, m = map(int, period.split("-"))
    k = y * 12 + (m - 1) + n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def month_index(period: str) -> int:
    y, m = map(int, period.split("-"))
    y0, m0 = map(int, FIRST_PERIOD.split("-"))
    return (y - y0) * 12 + (m - m0)


PERIODS = [add_months(FIRST_PERIOD, i) for i in range(N_MONTHS)]
LAST_PERIOD = PERIODS[-1]
FUTURE = [add_months(LAST_PERIOD, i + 1) for i in range(HORIZON)]


def fiscal_year(period: str) -> str:
    y, m = map(int, period.split("-"))
    start = y if m >= 4 else y - 1
    return f"{start}-{(start + 1) % 100:02d}"


CURRENT_FY = fiscal_year(LAST_PERIOD)          # cycle in progress (seats sanctioned, not yet certified)
COMPLETED_FYS = ["2023-24", "2024-25", "2025-26"]
NEXT_FY = "2027-28"                            # cycle that target-setting plans for
GAP_WINDOW = FUTURE[:12]                       # next 12 months of labour demand
CYCLE_WINDOW = [p for p in FUTURE if fiscal_year(p) == "2027-28"]
