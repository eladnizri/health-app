#!/usr/bin/env python3
"""הכל בפקודה אחת:  python app.py

1. מתחבר לגרמין (בפעם הראשונה ישאל אימייל/סיסמה, תומך MFA; אחר כך זוכר)
2. מושך את הימים שחסרים (ברירת מחדל: 30 אחורה)
3. מחשב הכל ופותח את הדשבורד בדפדפן

python app.py --days 90   כדי למשוך היסטוריה ארוכה יותר
python app.py --demo      כדי לראות את הדשבורד עם נתוני דמו, בלי חשבון גרמין
"""

import argparse
import os
import threading
import webbrowser


def main() -> None:
    parser = argparse.ArgumentParser(description="Garmin Metrics Analyzer - הכל בפקודה אחת")
    parser.add_argument("--days", type=int, default=30, help="כמה ימים אחורה למשוך")
    parser.add_argument("--demo", action="store_true", help="נתוני דמו בלי חשבון גרמין")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-sync", action="store_true", help="רק לפתוח את הדשבורד, בלי משיכה")
    args = parser.parse_args()

    if args.demo:
        os.environ["GARMIN_ANALYZER_DEMO"] = "1"
        from garmin_analyzer.config import DEMO_DB_PATH
        if not DEMO_DB_PATH.exists():
            from garmin_analyzer.demo import seed
            seed()
    elif not args.no_sync:
        # login (interactive on first run) + pull whatever is missing
        from garmin_analyzer.garmin_client import get_client
        from garmin_analyzer.sync import run_sync

        garmin = get_client()
        run_sync(days=args.days, garmin=garmin)

    url = f"http://127.0.0.1:{args.port}"
    print(f"\n  פותח את הדשבורד: {url}  (Ctrl+C לעצירה)\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("garmin_analyzer.web.main:app", host="127.0.0.1", port=args.port,
                log_level="warning")


if __name__ == "__main__":
    main()
