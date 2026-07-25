"""Personal correlation discovery between metrics.

Finds relationships in the user's own history, e.g. "כשאתה נרדם אחרי 00:30,
ה-HRV שלך יורד ב-15% בממוצע". Uses Pearson correlation over aligned day pairs;
some pairs are lagged (yesterday's stress vs. tonight's sleep).
"""

from __future__ import annotations

import datetime as dt
import math

from .config import CORRELATION_MIN_DAYS, CORRELATION_MIN_R


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return cov / (sx * sy)


def bedtime_hour(row: dict) -> float | None:
    """Bedtime as continuous hours; after-midnight times map past 24 (00:30→24.5)."""
    if not row.get("bedtime"):
        return None
    try:
        t = dt.datetime.fromisoformat(row["bedtime"])
    except ValueError:
        return None
    h = t.hour + t.minute / 60
    return h + 24 if h < 12 else h


# (x_metric, y_metric, lag_days, hebrew description of the pair)
# lag_days=1 means: x from day D, y from day D+1 (x affects the following night)
PAIRS = [
    ("bedtime_hour", "hrv_last_night", 0,
     "שעת ההירדמות מול ה-HRV באותו לילה"),
    ("sleep_duration_sec", "hrv_last_night", 0,
     "משך השינה מול ה-HRV באותו לילה"),
    ("sleep_duration_sec", "sleep_score", 0,
     "משך השינה מול ניקוד השינה"),
    ("stress_avg", "sleep_score", 1,
     "רמת ה-Stress ביום מול איכות השינה בלילה שאחריו"),
    ("stress_avg", "hrv_last_night", 1,
     "רמת ה-Stress ביום מול ה-HRV בלילה שאחריו"),
    ("steps", "sleep_score", 1,
     "כמות הצעדים ביום מול איכות השינה בלילה שאחריו"),
    ("hrv_last_night", "resting_hr", 0,
     "ה-HRV הלילי מול דופק המנוחה"),
    ("sleep_score", "bb_charged", 0,
     "ניקוד השינה מול טעינת ה-Body Battery בלילה"),
]


def _value(row: dict, metric: str) -> float | None:
    if metric == "bedtime_hour":
        return bedtime_hour(row)
    v = row.get(metric)
    return float(v) if v is not None else None


def _aligned(history: list[dict], x_metric: str, y_metric: str,
             lag: int) -> tuple[list[float], list[float]]:
    by_date = {r["date"]: r for r in history}
    xs, ys = [], []
    for row in history:
        x = _value(row, x_metric)
        if x is None:
            continue
        if lag == 0:
            y_row = row
        else:
            next_date = (dt.date.fromisoformat(row["date"]) + dt.timedelta(days=lag)).isoformat()
            y_row = by_date.get(next_date)
        if not y_row:
            continue
        y = _value(y_row, y_metric)
        if y is None:
            continue
        xs.append(x)
        ys.append(y)
    return xs, ys


def _strength(r: float) -> str:
    a = abs(r)
    if a >= 0.6:
        return "חזק"
    if a >= 0.4:
        return "בינוני"
    return "חלש"


def _describe(x_metric: str, y_metric: str, r: float,
              xs: list[float], ys: list[float]) -> str:
    """Concrete Hebrew sentence: compare y between low-x days and high-x days."""
    pairs_sorted = sorted(zip(xs, ys), key=lambda p: p[0])
    third = max(1, len(pairs_sorted) // 3)
    low_y = sum(y for _, y in pairs_sorted[:third]) / third
    high_y = sum(y for _, y in pairs_sorted[-third:]) / third

    fmt = {
        "bedtime_hour": lambda v: f"{int(v) % 24:02d}:{int(round((v % 1) * 60)):02d}",
        "sleep_duration_sec": lambda v: f"{v / 3600:.1f} שעות",
        "steps": lambda v: f"{v:,.0f} צעדים",
    }.get(x_metric, lambda v: f"{v:.0f}")
    low_x_label = fmt(sum(x for x, _ in pairs_sorted[:third]) / third)
    high_x_label = fmt(sum(x for x, _ in pairs_sorted[-third:]) / third)

    y_names = {
        "hrv_last_night": "ה-HRV הממוצע",
        "sleep_score": "ניקוד השינה הממוצע",
        "resting_hr": "דופק המנוחה הממוצע",
        "bb_charged": "טעינת ה-Body Battery הממוצעת",
    }
    y_name = y_names.get(y_metric, y_metric)
    x_names = {
        "bedtime_hour": "בימים שנרדמת מאוחר (סביב {high})",
        "sleep_duration_sec": "כשישנת יותר (סביב {high})",
        "sleep_score": "בלילות עם שינה טובה",
        "stress_avg": "אחרי ימים עם Stress גבוה (סביב {high})",
        "steps": "אחרי ימים פעילים (סביב {high})",
        "hrv_last_night": "בלילות עם HRV גבוה",
    }
    x_phrase = x_names.get(x_metric, x_metric).format(high=high_x_label, low=low_x_label)
    return (f"{x_phrase} {y_name} שלך היה {high_y:.0f}, "
            f"לעומת {low_y:.0f} בקצה השני (סביב {low_x_label}).")


def find_correlations(history: list[dict]) -> list[dict]:
    """All pair correlations that pass the sample-size and strength thresholds,
    strongest first."""
    results = []
    for x_metric, y_metric, lag, pair_label in PAIRS:
        xs, ys = _aligned(history, x_metric, y_metric, lag)
        if len(xs) < CORRELATION_MIN_DAYS:
            continue
        r = pearson(xs, ys)
        if r is None or abs(r) < CORRELATION_MIN_R:
            continue
        results.append({
            "pair": pair_label,
            "x": x_metric,
            "y": y_metric,
            "lag": lag,
            "r": round(r, 2),
            "n": len(xs),
            "strength": _strength(r),
            "direction": "positive" if r > 0 else "negative",
            "text": _describe(x_metric, y_metric, r, xs, ys),
        })
    results.sort(key=lambda c: -abs(c["r"]))
    return results
