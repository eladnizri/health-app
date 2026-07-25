"""Fetch daily metrics from Garmin Connect into the local SQLite database.

Usage:
    python -m garmin_analyzer.sync            # sync missing days (up to 30 back)
    python -m garmin_analyzer.sync --days 90  # backfill 90 days
    python -m garmin_analyzer.sync --force    # re-fetch even days already stored
"""

from __future__ import annotations

import argparse
import datetime as dt
import time

from . import db
from .config import DB_PATH, ensure_dirs


def _ms_to_iso(ms) -> str | None:
    if not ms:
        return None
    return dt.datetime.utcfromtimestamp(ms / 1000).isoformat(timespec="minutes")


def parse_sleep(data: dict) -> dict:
    out: dict = {}
    dto = (data or {}).get("dailySleepDTO") or {}
    if not dto:
        return out
    scores = dto.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    if overall.get("value") is not None:
        out["sleep_score"] = overall["value"]
    if dto.get("sleepTimeSeconds") is not None:
        out["sleep_duration_sec"] = dto["sleepTimeSeconds"]
    for col, key in [
        ("deep_sec", "deepSleepSeconds"),
        ("light_sec", "lightSleepSeconds"),
        ("rem_sec", "remSleepSeconds"),
        ("awake_sec", "awakeSleepSeconds"),
    ]:
        if dto.get(key) is not None:
            out[col] = dto[key]
    out["bedtime"] = _ms_to_iso(dto.get("sleepStartTimestampLocal"))
    out["wake_time"] = _ms_to_iso(dto.get("sleepEndTimestampLocal"))
    return out


def parse_hrv(data: dict) -> dict:
    out: dict = {}
    summary = (data or {}).get("hrvSummary") or {}
    if not summary:
        return out
    if summary.get("lastNightAvg") is not None:
        out["hrv_last_night"] = summary["lastNightAvg"]
    if summary.get("weeklyAvg") is not None:
        out["hrv_weekly_avg"] = summary["weeklyAvg"]
    if summary.get("status"):
        out["hrv_status"] = summary["status"]
    baseline = summary.get("baseline") or {}
    if baseline.get("balancedLow") is not None:
        out["hrv_balanced_low"] = baseline["balancedLow"]
    if baseline.get("balancedUpper") is not None:
        out["hrv_balanced_high"] = baseline["balancedUpper"]
    return out


def parse_heart_rate(data: dict, sleep_raw: dict | None) -> dict:
    """Resting HR plus average HR split into sleep window vs. awake hours."""
    out: dict = {}
    data = data or {}
    if data.get("restingHeartRate") is not None:
        out["resting_hr"] = data["restingHeartRate"]

    values = data.get("heartRateValues") or []
    samples = [(ts, hr) for ts, hr in values if hr is not None and ts is not None]
    if not samples:
        return out

    sleep_start = sleep_end = None
    dto = (sleep_raw or {}).get("dailySleepDTO") or {}
    if dto.get("sleepStartTimestampGMT") and dto.get("sleepEndTimestampGMT"):
        sleep_start, sleep_end = dto["sleepStartTimestampGMT"], dto["sleepEndTimestampGMT"]

    if sleep_start and sleep_end:
        in_sleep = [hr for ts, hr in samples if sleep_start <= ts <= sleep_end]
        awake = [hr for ts, hr in samples if not (sleep_start <= ts <= sleep_end)]
        if in_sleep:
            out["sleep_avg_hr"] = round(sum(in_sleep) / len(in_sleep), 1)
        if awake:
            out["day_active_avg_hr"] = round(sum(awake) / len(awake), 1)
    else:
        out["day_active_avg_hr"] = round(sum(h for _, h in samples) / len(samples), 1)
    return out


def parse_stress(data: dict) -> dict:
    out: dict = {}
    data = data or {}
    if data.get("avgStressLevel") is not None and data["avgStressLevel"] >= 0:
        out["stress_avg"] = data["avgStressLevel"]
    if data.get("maxStressLevel") is not None and data["maxStressLevel"] >= 0:
        out["stress_max"] = data["maxStressLevel"]
    return out


def parse_body_battery(day_entry: dict) -> dict:
    out: dict = {}
    day_entry = day_entry or {}
    if day_entry.get("charged") is not None:
        out["bb_charged"] = day_entry["charged"]
    if day_entry.get("drained") is not None:
        out["bb_drained"] = day_entry["drained"]
    levels = [
        point[1]
        for point in (day_entry.get("bodyBatteryValuesArray") or [])
        if isinstance(point, (list, tuple)) and len(point) > 1 and isinstance(point[1], (int, float))
    ]
    if levels:
        out["bb_high"] = max(levels)
        out["bb_low"] = min(levels)
    return out


def parse_summary(data: dict) -> dict:
    out: dict = {}
    data = data or {}
    if data.get("totalSteps") is not None:
        out["steps"] = data["totalSteps"]
    # user_summary carries body battery extremes even when the detailed
    # endpoint returns nothing
    if data.get("bodyBatteryHighestValue") is not None:
        out.setdefault("bb_high", data["bodyBatteryHighestValue"])
    if data.get("bodyBatteryLowestValue") is not None:
        out.setdefault("bb_low", data["bodyBatteryLowestValue"])
    if data.get("bodyBatteryChargedValue") is not None:
        out.setdefault("bb_charged", data["bodyBatteryChargedValue"])
    if data.get("bodyBatteryDrainedValue") is not None:
        out.setdefault("bb_drained", data["bodyBatteryDrainedValue"])
    return out


def _safe_fetch(label: str, fn, *args):
    try:
        return fn(*args)
    except Exception as exc:
        print(f"    ({label}: {type(exc).__name__} - מדלג)")
        return None


def sync_day(garmin, conn, date: dt.date) -> None:
    cdate = date.isoformat()
    values: dict = {"synced_at": dt.datetime.now().isoformat(timespec="seconds")}

    sleep_raw = _safe_fetch("sleep", garmin.get_sleep_data, cdate)
    if sleep_raw:
        db.save_raw(conn, cdate, "sleep", sleep_raw)
        values.update(parse_sleep(sleep_raw))

    hrv_raw = _safe_fetch("hrv", garmin.get_hrv_data, cdate)
    if hrv_raw:
        db.save_raw(conn, cdate, "hrv", hrv_raw)
        values.update(parse_hrv(hrv_raw))

    hr_raw = _safe_fetch("heart_rate", garmin.get_heart_rates, cdate)
    if hr_raw:
        db.save_raw(conn, cdate, "heart_rate", hr_raw)
        values.update(parse_heart_rate(hr_raw, sleep_raw))

    stress_raw = _safe_fetch("stress", garmin.get_stress_data, cdate)
    if stress_raw:
        db.save_raw(conn, cdate, "stress", stress_raw)
        values.update(parse_stress(stress_raw))

    bb_raw = _safe_fetch("body_battery", garmin.get_body_battery, cdate)
    if bb_raw:
        db.save_raw(conn, cdate, "body_battery", bb_raw)
        entry = bb_raw[0] if isinstance(bb_raw, list) and bb_raw else bb_raw
        if isinstance(entry, dict):
            values.update(parse_body_battery(entry))

    summary_raw = _safe_fetch("summary", garmin.get_user_summary, cdate)
    if summary_raw:
        db.save_raw(conn, cdate, "summary", summary_raw)
        values.update(parse_summary(summary_raw))

    db.upsert_day(conn, cdate, values)


def run_sync(days: int = 30, force: bool = False, garmin=None, db_path=None) -> int:
    """Sync the last `days` days. Skips days already in the DB unless force.
    Returns the number of days fetched."""
    from .garmin_client import get_client

    ensure_dirs()
    conn = db.connect(db_path or DB_PATH)
    today = dt.date.today()
    dates = [today - dt.timedelta(days=i) for i in range(days)]

    if not force:
        # Always re-fetch today and yesterday (data keeps updating), skip older
        # days that are already stored.
        existing = {r["date"] for r in db.get_all(conn) if r.get("synced_at")}
        dates = [d for d in dates if d.isoformat() not in existing or (today - d).days <= 1]

    if not dates:
        print("הכל מעודכן - אין ימים חדשים למשוך.")
        return 0

    garmin = garmin or get_client()
    print(f"מושך {len(dates)} ימים מ-Garmin Connect...")
    for i, date in enumerate(sorted(dates)):
        print(f"  [{i + 1}/{len(dates)}] {date.isoformat()}")
        sync_day(garmin, conn, date)
        time.sleep(0.5)  # be gentle with Garmin's servers
    print("סנכרון הושלם.")
    return len(dates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Garmin data to local DB")
    parser.add_argument("--days", type=int, default=30, help="how many days back")
    parser.add_argument("--force", action="store_true", help="re-fetch existing days")
    args = parser.parse_args()
    run_sync(days=args.days, force=args.force)


if __name__ == "__main__":
    main()
