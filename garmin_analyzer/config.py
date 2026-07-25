"""Paths and constants shared across the app."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GARMIN_ANALYZER_DATA", PROJECT_ROOT / "data"))
DB_PATH = Path(os.environ.get("GARMIN_ANALYZER_DB", DATA_DIR / "health.db"))
DEMO_DB_PATH = DATA_DIR / "demo.db"
TOKEN_DIR = Path(os.environ.get("GARMIN_ANALYZER_TOKENS", DATA_DIR / "tokens"))

# Rolling window (days) used to compute personal baselines
BASELINE_WINDOW = 30
# Minimum days of history required before baselines are considered meaningful
BASELINE_MIN_DAYS = 7

# Correlation analysis thresholds
CORRELATION_MIN_DAYS = 14
CORRELATION_MIN_R = 0.25


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
