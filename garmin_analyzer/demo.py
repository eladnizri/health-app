"""Generate realistic synthetic data so the dashboard can be explored before
the first real Garmin sync: python -m garmin_analyzer.demo"""

from __future__ import annotations

import datetime as dt
import random

from . import db
from .config import DEMO_DB_PATH, ensure_dirs


def seed(db_path=None, days: int = 90, seed_val: int = 42) -> None:
    ensure_dirs()
    rng = random.Random(seed_val)
    conn = db.connect(db_path or DEMO_DB_PATH)
    today = dt.date.today()

    for i in range(days, 0, -1):
        date = today - dt.timedelta(days=i - 1)
        # Weekly rhythm: weekends -> later bedtime; occasional "hard day"
        is_weekend = date.weekday() in (3, 4)  # Thu/Fri nights in IL
        hard_day = rng.random() < 0.15

        bed_hour = 23.0 + (1.5 if is_weekend else 0) + rng.gauss(0, 0.6)
        duration_h = max(4.5, min(9.5, rng.gauss(7.2, 0.7) - (bed_hour - 23) * 0.35))
        duration = int(duration_h * 3600)

        # Late bedtime and hard days depress HRV; long sleep helps it
        hrv = 52 + (duration_h - 7.2) * 2.5 - max(0, bed_hour - 23.3) * 4 \
            - (10 if hard_day else 0) + rng.gauss(0, 4)
        hrv = max(25, hrv)

        sleep_score = int(max(35, min(98, 60 + (duration_h - 6) * 9
                                      - (12 if hard_day else 0) + rng.gauss(0, 6))))
        rhr = int(round(52 - (hrv - 52) * 0.25 + rng.gauss(0, 1.5)))
        sleep_hr = round(rhr + 2 + (4 if hard_day else 0) + rng.gauss(0, 1.5), 1)
        day_hr = round(rhr + 22 + rng.gauss(0, 3), 1)

        stress = int(max(12, min(85, 30 + (18 if hard_day else 0)
                                 - (hrv - 52) * 0.4 + rng.gauss(0, 6))))
        bb_charged = int(max(20, min(100, 40 + (sleep_score - 60) * 0.7 + rng.gauss(0, 6))))
        bb_high = min(100, bb_charged + rng.randint(0, 15))
        bb_low = max(5, bb_high - stress - rng.randint(10, 30))
        steps = int(max(2000, rng.gauss(9000, 2500) + (3000 if hard_day else 0)))

        deep = int(duration * rng.uniform(0.15, 0.22))
        rem = int(duration * rng.uniform(0.18, 0.26))
        awake = int(duration * rng.uniform(0.02, 0.07))
        light = duration - deep - rem - awake

        bed_dt = dt.datetime.combine(date - dt.timedelta(days=1), dt.time(0)) \
            + dt.timedelta(hours=bed_hour)
        wake_dt = bed_dt + dt.timedelta(seconds=duration + awake)

        db.upsert_day(conn, date.isoformat(), {
            "sleep_score": sleep_score,
            "sleep_duration_sec": duration,
            "deep_sec": deep, "light_sec": light, "rem_sec": rem, "awake_sec": awake,
            "bedtime": bed_dt.isoformat(timespec="minutes"),
            "wake_time": wake_dt.isoformat(timespec="minutes"),
            "hrv_last_night": round(hrv, 0),
            "hrv_weekly_avg": round(hrv + rng.gauss(0, 1.5), 0),
            "hrv_status": "BALANCED" if hrv > 45 else "LOW",
            "resting_hr": rhr,
            "sleep_avg_hr": sleep_hr,
            "day_active_avg_hr": day_hr,
            "bb_charged": bb_charged, "bb_drained": bb_charged + rng.randint(-10, 10),
            "bb_high": bb_high, "bb_low": bb_low,
            "stress_avg": stress, "stress_max": min(99, stress + rng.randint(20, 40)),
            "steps": steps,
            "synced_at": dt.datetime.now().isoformat(timespec="seconds"),
        })
    conn.close()
    print(f"נוצרו {days} ימי דמו ב-{db_path or DEMO_DB_PATH}")


if __name__ == "__main__":
    seed()
