"""SQLite storage for daily Garmin metrics.

One row per calendar day in `daily_metrics`; raw API payloads are kept in
`raw_data` so history can be re-parsed without hitting Garmin again.
"""

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_metrics (
    date TEXT PRIMARY KEY,              -- YYYY-MM-DD

    -- Sleep
    sleep_score INTEGER,
    sleep_duration_sec INTEGER,
    deep_sec INTEGER,
    light_sec INTEGER,
    rem_sec INTEGER,
    awake_sec INTEGER,
    bedtime TEXT,                       -- ISO local datetime
    wake_time TEXT,                     -- ISO local datetime

    -- HRV
    hrv_last_night REAL,                -- ms
    hrv_weekly_avg REAL,
    hrv_status TEXT,                    -- Garmin: BALANCED / UNBALANCED / LOW / POOR
    hrv_balanced_low REAL,              -- Garmin's own personal baseline range
    hrv_balanced_high REAL,

    -- Heart rate
    resting_hr INTEGER,
    sleep_avg_hr REAL,                  -- avg HR inside the sleep window
    day_active_avg_hr REAL,             -- avg HR while awake (walking / daily activity)

    -- Body Battery
    bb_charged INTEGER,                 -- overnight charge
    bb_drained INTEGER,                 -- daytime drain
    bb_high INTEGER,
    bb_low INTEGER,

    -- Stress
    stress_avg INTEGER,
    stress_max INTEGER,

    -- Activity context
    steps INTEGER,

    synced_at TEXT
);

CREATE TABLE IF NOT EXISTS raw_data (
    date TEXT NOT NULL,
    kind TEXT NOT NULL,                 -- sleep / hrv / heart_rate / stress / body_battery / summary
    payload TEXT NOT NULL,
    PRIMARY KEY (date, kind)
);
"""

METRIC_COLUMNS = [
    "sleep_score", "sleep_duration_sec", "deep_sec", "light_sec", "rem_sec",
    "awake_sec", "bedtime", "wake_time",
    "hrv_last_night", "hrv_weekly_avg", "hrv_status",
    "hrv_balanced_low", "hrv_balanced_high",
    "resting_hr", "sleep_avg_hr", "day_active_avg_hr",
    "bb_charged", "bb_drained", "bb_high", "bb_low",
    "stress_avg", "stress_max", "steps", "synced_at",
]


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_day(conn: sqlite3.Connection, date: str, values: dict) -> None:
    """Insert or update a day's row. Only provided keys are written, so a
    partial re-sync never wipes metrics fetched earlier."""
    cols = [c for c in METRIC_COLUMNS if c in values]
    if not cols:
        return
    conn.execute(
        f"INSERT INTO daily_metrics (date, {', '.join(cols)}) "
        f"VALUES (?, {', '.join('?' for _ in cols)}) "
        f"ON CONFLICT(date) DO UPDATE SET "
        + ", ".join(f"{c}=excluded.{c}" for c in cols),
        [date] + [values[c] for c in cols],
    )
    conn.commit()


def save_raw(conn: sqlite3.Connection, date: str, kind: str, payload) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO raw_data (date, kind, payload) VALUES (?, ?, ?)",
        (date, kind, json.dumps(payload, ensure_ascii=False, default=str)),
    )
    conn.commit()


def get_day(conn: sqlite3.Connection, date: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM daily_metrics WHERE date = ?", (date,)
    ).fetchone()
    return dict(row) if row else None


def get_range(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM daily_metrics WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM daily_metrics ORDER BY date").fetchall()
    return [dict(r) for r in rows]


def latest_date(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(date) AS d FROM daily_metrics").fetchone()
    return row["d"] if row and row["d"] else None
