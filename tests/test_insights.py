import datetime as dt

from garmin_analyzer.insights import analyze_day


def build_history(days=30, **overrides):
    """Stable, healthy history; the last day can be overridden."""
    start = dt.date(2026, 6, 1)
    history = []
    for i in range(days):
        history.append({
            "date": (start + dt.timedelta(days=i)).isoformat(),
            "hrv_last_night": 50.0,
            "resting_hr": 52,
            "sleep_avg_hr": 50.0,
            "sleep_score": 85,
            "sleep_duration_sec": int(7.5 * 3600),
            "bb_charged": 70,
            "stress_avg": 30,
        })
    history[-1].update(overrides)
    return history


def test_good_day_is_ready():
    history = build_history()
    insight = analyze_day(history[-1], history)
    assert insight["status"] == "ready"
    assert insight["score"] >= 80
    assert any(f["sentiment"] == "good" for f in insight["findings"])


def test_bad_day_recommends_rest():
    history = build_history(
        hrv_last_night=40.0,       # -20% HRV
        sleep_avg_hr=55.0,         # +10% sleep HR
        sleep_score=55,
        sleep_duration_sec=int(5 * 3600),
    )
    insight = analyze_day(history[-1], history)
    assert insight["status"] == "rest"
    # The headline finding should mention the HRV drop with the percentage
    hrv_findings = [f for f in insight["findings"] if f["metric"] == "HRV"]
    assert hrv_findings and hrv_findings[0]["sentiment"] == "bad"
    assert "20%" in hrv_findings[0]["text"]


def test_moderate_day():
    history = build_history(hrv_last_night=44.0, sleep_score=70)  # -12% HRV
    insight = analyze_day(history[-1], history)
    assert insight["status"] == "moderate"


def test_no_data_day():
    history = build_history()
    empty = {"date": "2026-07-10"}
    insight = analyze_day(empty, history)
    assert insight["status"] == "no_data"
    assert insight["score"] is None


def test_problems_sorted_first():
    history = build_history(hrv_last_night=40.0)
    insight = analyze_day(history[-1], history)
    sentiments = [f["sentiment"] for f in insight["findings"]]
    assert sentiments.index("bad") == 0


def test_short_history_still_works():
    history = build_history(days=3)
    insight = analyze_day(history[-1], history)
    # No baselines yet, but sleep score data still yields an insight
    assert insight["status"] in ("ready", "moderate", "rest")
