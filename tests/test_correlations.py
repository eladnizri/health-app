import datetime as dt
import random

from garmin_analyzer.correlations import bedtime_hour, find_correlations, pearson


def test_pearson_perfect():
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    assert abs(pearson([1, 2, 3], [6, 4, 2]) + 1.0) < 1e-9


def test_pearson_constant_returns_none():
    assert pearson([1, 1, 1], [2, 4, 6]) is None


def test_bedtime_hour_after_midnight():
    assert bedtime_hour({"bedtime": "2026-07-01T00:30"}) == 24.5
    assert bedtime_hour({"bedtime": "2026-07-01T23:00"}) == 23.0
    assert bedtime_hour({"bedtime": None}) is None


def test_finds_negative_bedtime_hrv_link():
    rng = random.Random(1)
    start = dt.date(2026, 5, 1)
    history = []
    for i in range(40):
        late = rng.uniform(0, 3)  # hours past 22:30
        bed = dt.datetime(2026, 5, 1, 22, 30) + dt.timedelta(days=i, hours=late)
        history.append({
            "date": (start + dt.timedelta(days=i + 1)).isoformat(),
            "bedtime": bed.isoformat(timespec="minutes"),
            "hrv_last_night": 55 - late * 5 + rng.gauss(0, 1),
        })
    results = find_correlations(history)
    match = [c for c in results if c["x"] == "bedtime_hour" and c["y"] == "hrv_last_night"]
    assert match and match[0]["direction"] == "negative"
    assert match[0]["n"] == 40


def test_lagged_stress_sleep_alignment():
    start = dt.date(2026, 5, 1)
    history = []
    for i in range(30):
        stress = 20 + (i % 2) * 40  # alternating stress
        history.append({
            "date": (start + dt.timedelta(days=i)).isoformat(),
            "stress_avg": stress,
        })
        # next day's sleep reflects yesterday's stress (inverse)
        if history and i > 0:
            history[i]["sleep_score"] = 90 - (history[i - 1]["stress_avg"] - 20)
    results = find_correlations(history)
    match = [c for c in results if c["x"] == "stress_avg" and c["y"] == "sleep_score"]
    assert match and match[0]["direction"] == "negative"
    assert abs(match[0]["r"]) > 0.9


def test_insufficient_data_returns_empty():
    history = [{"date": f"2026-07-{d:02d}", "sleep_score": 80, "hrv_last_night": 50}
               for d in range(1, 6)]
    assert find_correlations(history) == []
