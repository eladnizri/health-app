#!/usr/bin/env python3
"""Start the dashboard:  python run.py [--demo] [--lan] [--port 8765]

--demo seeds 90 days of synthetic data and serves it, so the UI can be
explored before connecting a real Garmin account.

--lan binds to all network interfaces so you can open the dashboard from your
phone on the same Wi-Fi (and add it to the home screen as an app). Prints the
exact address to type on the phone.
"""

import argparse
import os
import socket


def local_ip() -> str:
    """Best-effort LAN IP of this machine (the address the phone should use)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packets sent; just picks the route
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Garmin Metrics Analyzer")
    parser.add_argument("--demo", action="store_true", help="run with synthetic demo data")
    parser.add_argument("--lan", action="store_true",
                        help="expose on the local network (open from your phone)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default=None,
                        help="bind address (overrides --lan)")
    args = parser.parse_args()

    if args.demo:
        os.environ["GARMIN_ANALYZER_DEMO"] = "1"
        from garmin_analyzer.config import DEMO_DB_PATH
        if not DEMO_DB_PATH.exists():
            from garmin_analyzer.demo import seed
            seed()

    host = args.host or ("0.0.0.0" if args.lan else "127.0.0.1")

    print()
    if host == "0.0.0.0":
        print(f"  על המחשב הזה:      http://127.0.0.1:{args.port}")
        print(f"  מהטלפון (Wi-Fi):   http://{local_ip()}:{args.port}")
        print("  בטלפון: פותחים את הכתובת בדפדפן ואז 'הוסף למסך הבית'.")
    else:
        print(f"  הדשבורד זמין בכתובת: http://127.0.0.1:{args.port}")
    print()

    import uvicorn
    uvicorn.run("garmin_analyzer.web.main:app", host=host, port=args.port)


if __name__ == "__main__":
    main()
