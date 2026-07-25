"""Morning recovery insights engine.

Compares today's overnight metrics against the personal rolling baselines and
produces a plain-Hebrew explanation of recovery state plus a recommendation,
e.g. "ה-HRV נמוך ב-12% והדופק בשינה היה גבוה מהרגיל - מומלץ יום רגוע".
"""

from __future__ import annotations

from .baseline import compute_baselines, deviation_pct, hrv_balanced_range


def _fmt_hours(seconds) -> str:
    if seconds is None:
        return "?"
    h, m = int(seconds) // 3600, (int(seconds) % 3600) // 60
    return f"{h}:{m:02d}"


def analyze_day(day: dict, history: list[dict]) -> dict:
    """Build the morning insight for `day` given full history (list of day rows)."""
    baselines = compute_baselines(history, day["date"])
    findings: list[dict] = []
    score = 100
    has_data = False

    # --- HRV ---
    hrv = day.get("hrv_last_night")
    hrv_base = baselines.get("hrv_last_night")
    hrv_dev = deviation_pct(hrv, hrv_base)
    balanced = hrv_balanced_range(day, baselines)
    if hrv is not None:
        has_data = True
        if hrv_dev is not None:
            if hrv_dev <= -15:
                score -= 30
                findings.append({
                    "metric": "HRV", "sentiment": "bad",
                    "text": f"ה-HRV הלילה ({hrv:.0f}ms) נמוך ב-{abs(hrv_dev):.0f}% מהבסיס האישי שלך ({hrv_base['mean']:.0f}ms) - סימן לעומס או התאוששות חלקית",
                })
            elif hrv_dev <= -8:
                score -= 15
                findings.append({
                    "metric": "HRV", "sentiment": "warn",
                    "text": f"ה-HRV הלילה ({hrv:.0f}ms) נמוך ב-{abs(hrv_dev):.0f}% מהבסיס שלך ({hrv_base['mean']:.0f}ms)",
                })
            elif hrv_dev >= 12:
                findings.append({
                    "metric": "HRV", "sentiment": "good",
                    "text": f"ה-HRV הלילה ({hrv:.0f}ms) גבוה ב-{hrv_dev:.0f}% מהבסיס שלך - התאוששות טובה",
                })
            else:
                findings.append({
                    "metric": "HRV", "sentiment": "good",
                    "text": f"ה-HRV הלילה ({hrv:.0f}ms) בטווח המאוזן האישי שלך",
                })
        elif balanced:
            low, high = balanced
            if hrv < low:
                score -= 20
                findings.append({
                    "metric": "HRV", "sentiment": "bad",
                    "text": f"ה-HRV הלילה ({hrv:.0f}ms) מתחת לטווח המאוזן שלך ({low:.0f}-{high:.0f}ms)",
                })
            else:
                findings.append({
                    "metric": "HRV", "sentiment": "good",
                    "text": f"ה-HRV הלילה ({hrv:.0f}ms) בתוך הטווח המאוזן שלך ({low:.0f}-{high:.0f}ms)",
                })

    # --- Sleep heart rate ---
    shr = day.get("sleep_avg_hr")
    shr_dev = deviation_pct(shr, baselines.get("sleep_avg_hr"))
    if shr is not None:
        has_data = True
        if shr_dev is not None and shr_dev >= 8:
            score -= 20
            findings.append({
                "metric": "Sleep HR", "sentiment": "bad",
                "text": f"הדופק הממוצע בשינה ({shr:.0f}) היה גבוה ב-{shr_dev:.0f}% מהרגיל - הגוף עבד קשה בלילה",
            })
        elif shr_dev is not None and shr_dev >= 4:
            score -= 10
            findings.append({
                "metric": "Sleep HR", "sentiment": "warn",
                "text": f"הדופק בשינה ({shr:.0f}) מעט גבוה מהרגיל (+{shr_dev:.0f}%)",
            })

    # --- Resting HR ---
    rhr = day.get("resting_hr")
    rhr_dev = deviation_pct(rhr, baselines.get("resting_hr"))
    if rhr is not None and rhr_dev is not None:
        has_data = True
        if rhr_dev >= 8:
            score -= 15
            findings.append({
                "metric": "Resting HR", "sentiment": "bad",
                "text": f"דופק המנוחה ({rhr}) גבוה ב-{rhr_dev:.0f}% מהבסיס שלך",
            })
        elif rhr_dev >= 4:
            score -= 8
            findings.append({
                "metric": "Resting HR", "sentiment": "warn",
                "text": f"דופק המנוחה ({rhr}) מעט גבוה מהרגיל (+{rhr_dev:.0f}%)",
            })
        elif rhr_dev <= -4:
            findings.append({
                "metric": "Resting HR", "sentiment": "good",
                "text": f"דופק המנוחה ({rhr}) נמוך מהרגיל - סימן טוב",
            })

    # --- Sleep quality ---
    sleep_score = day.get("sleep_score")
    duration = day.get("sleep_duration_sec")
    if sleep_score is not None:
        has_data = True
        if sleep_score < 60:
            score -= 15
            findings.append({
                "metric": "Sleep", "sentiment": "bad",
                "text": f"ניקוד השינה נמוך ({sleep_score}) - שינה של {_fmt_hours(duration)} שעות",
            })
        elif sleep_score < 75:
            score -= 8
            findings.append({
                "metric": "Sleep", "sentiment": "warn",
                "text": f"ניקוד שינה בינוני ({sleep_score}), {_fmt_hours(duration)} שעות שינה",
            })
        else:
            findings.append({
                "metric": "Sleep", "sentiment": "good",
                "text": f"שינה טובה: ניקוד {sleep_score}, {_fmt_hours(duration)} שעות",
            })
    if duration is not None and duration < 6 * 3600:
        score -= 10
        findings.append({
            "metric": "Sleep", "sentiment": "warn",
            "text": f"ישנת רק {_fmt_hours(duration)} שעות - פחות מ-6 שעות",
        })

    # --- Body Battery overnight charge ---
    bb = day.get("bb_charged")
    bb_dev = deviation_pct(bb, baselines.get("bb_charged"))
    if bb is not None:
        has_data = True
        if bb_dev is not None and bb_dev <= -25:
            score -= 10
            findings.append({
                "metric": "Body Battery", "sentiment": "warn",
                "text": f"ה-Body Battery נטען רק ב-{bb} נקודות בלילה ({abs(bb_dev):.0f}% פחות מהרגיל)",
            })
        elif bb_dev is not None and bb_dev >= 15:
            findings.append({
                "metric": "Body Battery", "sentiment": "good",
                "text": f"טעינת Body Battery מצוינת בלילה (+{bb})",
            })

    if not has_data:
        return {
            "date": day.get("date"), "status": "no_data", "score": None,
            "title": "אין מספיק נתונים להיום",
            "recommendation": "בצע סנכרון מול Garmin כדי לקבל תובנות בוקר.",
            "findings": [], "baselines": {},
        }

    score = max(0, min(100, score))
    if score >= 80:
        status, title = "ready", "התאוששות טובה - מוכן ליום מלא"
        recommendation = "הגוף התאושש היטב. אפשר להעמיס היום - אימון, עבודה אינטנסיבית, הכל פתוח."
    elif score >= 60:
        status, title = "moderate", "התאוששות חלקית"
        recommendation = "הגוף התאושש חלקית. עדיף יום מתון - פעילות קלה עד בינונית והקשבה לגוף."
    else:
        status, title = "rest", "מומלץ יום רגוע"
        recommendation = "הסימנים מצביעים על עומס. מומלץ יום רגוע: שינה מוקדמת, הליכה קלה במקום אימון, והרבה מים."

    # Order findings: problems first
    order = {"bad": 0, "warn": 1, "good": 2}
    findings.sort(key=lambda f: order.get(f["sentiment"], 3))

    return {
        "date": day.get("date"),
        "status": status,
        "score": score,
        "title": title,
        "recommendation": recommendation,
        "findings": findings,
        "hrv_balanced_range": balanced,
        "baselines": {
            k: {"mean": round(v["mean"], 1), "low": round(v["low"], 1),
                "high": round(v["high"], 1), "n": v["n"]}
            for k, v in baselines.items()
        },
    }
