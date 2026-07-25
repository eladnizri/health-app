#!/usr/bin/env python3
"""Start the dashboard:  python run.py [--demo] [--port 8765]

--demo seeds 90 days of synthetic data and serves it, so the UI can be
explored before connecting a real Garmin account.
"""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Garmin Metrics Analyzer")
    parser.add_argument("--demo", action="store_true", help="run with synthetic demo data")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.demo:
        os.environ["GARMIN_ANALYZER_DEMO"] = "1"
        from garmin_analyzer.config import DEMO_DB_PATH
        if not DEMO_DB_PATH.exists():
            from garmin_analyzer.demo import seed
            seed()

    import uvicorn
    print(f"\n  הדשבורד זמין בכתובת: http://{args.host}:{args.port}\n")
    uvicorn.run("garmin_analyzer.web.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
