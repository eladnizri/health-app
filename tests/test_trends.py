import datetime as dt

from garmin_analyzer.trends import aggregate, build_trends, with_deltas


def week_of(days_rows):
    start = dt.date(2026, 6, 1)  # Monday
    return [
        {"date": (start + dt.timedelta(days=i)).isoformat(), **row}
        for i, row in enumerate(days_rows)
    ]


def test_weekly_grouping():
    history = week_of([{"sleep_score": 80}] * 14)
    periods = aggregate(history, "week")
    assert len(periods) == 2
    assert periods[0]["days"] == 7
    assert periods[0]["sleep_score"] == 80


def test_monthly_grouping():
    history = week_of([{"sleep_score": 80}] * 40)
    periods = aggregate(history, "month")
    assert [p["period"] for p in periods] == ["2026-06", "2026-07"]


def test_deltas():
    history = week_of([{"hrv_last_night": 50}] * 7 + [{"hrv_last_night": 55}] * 7)
    periods = with_deltas(aggregate(history, "week"))
    assert periods[0]["deltas"] == {}
    assert periods[1]["deltas"]["hrv_last_night"] == 10.0


def test_summary_hebrew_lines():
    history = week_of([{"hrv_last_night": 50, "sleep_score": 80}] * 7
                      + [{"hrv_last_night": 40, "sleep_score": 80}] * 7)
    trends = build_trends(history, "week")
    assert any("HRV" in line and "20%" in line for line in trends["summary"])


def test_missing_metric_is_none():
    history = week_of([{"sleep_score": 80}] * 7)
    periods = aggregate(history, "week")
    assert periods[0]["hrv_last_night"] is None
