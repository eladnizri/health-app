from pathlib import Path

from garmin_analyzer import db


def test_partial_upsert_preserves_existing(tmp_path: Path):
    conn = db.connect(tmp_path / "t.db")
    db.upsert_day(conn, "2026-07-01", {"sleep_score": 80, "hrv_last_night": 50})
    db.upsert_day(conn, "2026-07-01", {"resting_hr": 52})  # partial update
    row = db.get_day(conn, "2026-07-01")
    assert row["sleep_score"] == 80
    assert row["hrv_last_night"] == 50
    assert row["resting_hr"] == 52


def test_range_and_latest(tmp_path: Path):
    conn = db.connect(tmp_path / "t.db")
    for d in ["2026-07-01", "2026-07-02", "2026-07-05"]:
        db.upsert_day(conn, d, {"sleep_score": 70})
    assert db.latest_date(conn) == "2026-07-05"
    assert [r["date"] for r in db.get_range(conn, "2026-07-01", "2026-07-02")] == [
        "2026-07-01", "2026-07-02"]


def test_raw_roundtrip(tmp_path: Path):
    conn = db.connect(tmp_path / "t.db")
    db.save_raw(conn, "2026-07-01", "sleep", {"a": 1})
    row = conn.execute("SELECT payload FROM raw_data WHERE date='2026-07-01'").fetchone()
    assert row["payload"] == '{"a": 1}'
