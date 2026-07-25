"""Weekly / monthly trend aggregation over the local history."""

from __future__ import annotations

import datetime as dt
from statistics import mean

TREND_METRICS = [
    "sleep_score", "sleep_duration_sec", "hrv_last_night", "resting_hr",
    "sleep_avg_hr", "day_active_avg_hr", "stress_avg", "bb_charged", "steps",
]

# metric -> (label, is higher better; None = neutral)
METRIC_DIRECTION = {
    "sleep_score": True,
    "sleep_duration_sec": True,
    "hrv_last_night": True,
    "resting_hr": False,
    "sleep_avg_hr": False,
    "day_active_avg_hr": None,
    "stress_avg": False,
    "bb_charged": True,
    "steps": True,
}

METRIC_LABELS = {
    "sleep_score": "Sleep Score",
    "sleep_duration_sec": "משך שינה",
    "hrv_last_night": "HRV",
    "resting_hr": "Resting HR",
    "sleep_avg_hr": "דופק בשינה",
    "day_active_avg_hr": "דופק פעילות יומית",
    "stress_avg": "Stress",
    "bb_charged": "טעינת Body Battery",
    "steps": "צעדים",
}


def _period_key(date_str: str, granularity: str) -> str:
    d = dt.date.fromisoformat(date_str)
    if granularity == "week":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return date_str[:7]  # YYYY-MM


def aggregate(history: list[dict], granularity: str = "week") -> list[dict]:
    """Group daily rows into weekly/monthly averages, chronological order."""
    groups: dict[str, list[dict]] = {}
    for row in history:
        groups.setdefault(_period_key(row["date"], granularity), []).append(row)

    periods = []
    for key in sorted(groups):
        rows = groups[key]
        entry: dict = {"period": key, "days": len(rows),
                       "start": rows[0]["date"], "end": rows[-1]["date"]}
        for metric in TREND_METRICS:
            vals = [r[metric] for r in rows if r.get(metric) is not None]
            entry[metric] = round(mean(vals), 1) if vals else None
        periods.append(entry)
    return periods


def with_deltas(periods: list[dict]) -> list[dict]:
    """Attach % change vs the previous period for each metric."""
    for i, p in enumerate(periods):
        deltas = {}
        if i > 0:
            prev = periods[i - 1]
            for metric in TREND_METRICS:
                cur, before = p.get(metric), prev.get(metric)
                if cur is not None and before:
                    deltas[metric] = round((cur - before) / before * 100, 1)
        p["deltas"] = deltas
    return periods


def summarize_latest(periods: list[dict], granularity: str) -> list[str]:
    """Hebrew one-liners about how the latest full period compares to the one before."""
    if len(periods) < 2:
        return []
    latest = periods[-1]
    name = "השבוע" if granularity == "week" else "החודש"
    lines = []
    for metric, delta in sorted(latest.get("deltas", {}).items(),
                                key=lambda kv: -abs(kv[1])):
        if abs(delta) < 3:
            continue
        label = METRIC_LABELS[metric]
        direction = "עלה" if delta > 0 else "ירד"
        better = METRIC_DIRECTION[metric]
        if better is None:
            tone = ""
        elif (delta > 0) == better:
            tone = " - מגמה חיובית"
        else:
            tone = " - שווה תשומת לב"
        lines.append(f"{label} {direction} ב-{abs(delta):.0f}% {name} לעומת התקופה הקודמת{tone}")
    return lines[:5]


def build_trends(history: list[dict], granularity: str = "week") -> dict:
    periods = with_deltas(aggregate(history, granularity))
    return {
        "granularity": granularity,
        "periods": periods,
        "summary": summarize_latest(periods, granularity),
    }
