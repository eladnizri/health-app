"""Personal baselines: rolling statistics per metric.

For each metric we compute mean and standard deviation over a rolling window
(default 30 days, excluding the day being evaluated), which defines the
personal "normal" range used by the insights engine. For HRV, Garmin's own
balanced range is preferred when present; otherwise mean±std of the window.
"""

from __future__ import annotations

from statistics import mean, pstdev

from .config import BASELINE_MIN_DAYS, BASELINE_WINDOW

# Metrics that get a rolling baseline
BASELINE_METRICS = [
    "hrv_last_night",
    "resting_hr",
    "sleep_avg_hr",
    "sleep_score",
    "sleep_duration_sec",
    "bb_charged",
    "stress_avg",
]


def _window_values(history: list[dict], metric: str, before_date: str,
                   window: int = BASELINE_WINDOW) -> list[float]:
    vals = [
        row[metric]
        for row in history
        if row["date"] < before_date and row.get(metric) is not None
    ]
    return [float(v) for v in vals[-window:]]


def metric_baseline(history: list[dict], metric: str, before_date: str,
                    window: int = BASELINE_WINDOW) -> dict | None:
    """Mean/std/count for `metric` over the window ending before `before_date`.
    Returns None when there is not enough history to be meaningful."""
    vals = _window_values(history, metric, before_date, window)
    if len(vals) < BASELINE_MIN_DAYS:
        return None
    avg = mean(vals)
    std = pstdev(vals)
    return {"mean": avg, "std": std, "n": len(vals), "low": avg - std, "high": avg + std}


def compute_baselines(history: list[dict], for_date: str) -> dict:
    """Baselines for every metric, keyed by metric name (missing ones omitted)."""
    out = {}
    for metric in BASELINE_METRICS:
        b = metric_baseline(history, metric, for_date)
        if b:
            out[metric] = b
    return out


def hrv_balanced_range(day: dict, baselines: dict) -> tuple[float, float] | None:
    """Personal balanced HRV range: Garmin's if synced, else computed mean±std."""
    if day.get("hrv_balanced_low") and day.get("hrv_balanced_high"):
        return float(day["hrv_balanced_low"]), float(day["hrv_balanced_high"])
    b = baselines.get("hrv_last_night")
    if b:
        return round(b["low"], 1), round(b["high"], 1)
    return None


def deviation_pct(value: float | None, baseline: dict | None) -> float | None:
    """Signed % deviation of value from the baseline mean."""
    if value is None or not baseline or not baseline["mean"]:
        return None
    return round((value - baseline["mean"]) / baseline["mean"] * 100, 1)
