import datetime as dt

from garmin_analyzer.baseline import (
    compute_baselines,
    deviation_pct,
    hrv_balanced_range,
    metric_baseline,
)


def make_history(days=30, hrv=50.0, rhr=52):
    start = dt.date(2026, 6, 1)
    return [
        {"date": (start + dt.timedelta(days=i)).isoformat(),
         "hrv_last_night": hrv, "resting_hr": rhr}
        for i in range(days)
    ]


def test_baseline_mean():
    history = make_history(30, hrv=50.0)
    b = metric_baseline(history, "hrv_last_night", "2026-07-01")
    assert b is not None
    assert b["mean"] == 50.0
    assert b["n"] == 30


def test_baseline_excludes_target_day_and_future():
    history = make_history(10, hrv=50.0)
    # Day 5 evaluated -> only days before it count
    b = metric_baseline(history, "hrv_last_night", history[5]["date"])
    assert b is None or b["n"] == 5  # 5 prior days < BASELINE_MIN_DAYS -> None
    assert metric_baseline(history, "hrv_last_night", history[9]["date"])["n"] == 9


def test_baseline_insufficient_history():
    assert metric_baseline(make_history(3), "hrv_last_night", "2026-07-01") is None


def test_deviation_pct():
    b = {"mean": 50.0, "std": 5.0, "n": 30, "low": 45.0, "high": 55.0}
    assert deviation_pct(44.0, b) == -12.0
    assert deviation_pct(55.0, b) == 10.0
    assert deviation_pct(None, b) is None


def test_hrv_balanced_range_prefers_garmin():
    day = {"hrv_balanced_low": 42, "hrv_balanced_high": 58}
    assert hrv_balanced_range(day, {}) == (42.0, 58.0)


def test_hrv_balanced_range_computed_fallback():
    history = make_history(30, hrv=50.0)
    baselines = compute_baselines(history, "2026-07-01")
    low, high = hrv_balanced_range({}, baselines)
    assert low == high == 50.0  # zero variance history
