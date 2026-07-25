"""FastAPI app serving the dashboard and the JSON API.

Run via:  python run.py [--demo] [--port 8765]
"""

from __future__ import annotations

import datetime as dt
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import db
from ..config import DB_PATH, DEMO_DB_PATH, ensure_dirs
from ..correlations import find_correlations
from ..insights import analyze_day
from ..trends import build_trends

WEB_DIR = Path(__file__).parent
DEMO_MODE = os.environ.get("GARMIN_ANALYZER_DEMO") == "1"

app = FastAPI(title="Garmin Metrics Analyzer")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


def _db_path() -> Path:
    return DEMO_DB_PATH if DEMO_MODE else DB_PATH


def _conn():
    ensure_dirs()
    return db.connect(_db_path())


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "templates" / "index.html")


@app.get("/sw.js")
def service_worker():
    # Served from root so the worker's scope covers the whole app, not /static.
    return FileResponse(
        WEB_DIR / "static" / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(
        WEB_DIR / "static" / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/api/status")
def status():
    from ..garmin_client import has_saved_tokens

    conn = _conn()
    try:
        rows = db.get_all(conn)
        return {
            "demo": DEMO_MODE,
            "days": len(rows),
            "latest": db.latest_date(conn),
            "logged_in": has_saved_tokens(),
            "sync": SYNC.snapshot(),
            "login": LOGIN.snapshot(),
        }
    finally:
        conn.close()


@app.get("/api/today")
def today():
    conn = _conn()
    try:
        history = db.get_all(conn)
        if not history:
            return {"insight": None, "day": None}
        day = history[-1]
        return {"insight": analyze_day(day, history), "day": day}
    finally:
        conn.close()


@app.get("/api/history")
def history(days: int = 30):
    from ..baseline import metric_baseline

    conn = _conn()
    try:
        latest = db.latest_date(conn)
        if not latest:
            return {"rows": []}
        start = (dt.date.fromisoformat(latest) - dt.timedelta(days=days - 1)).isoformat()
        rows = db.get_range(conn, start, latest)
        # Fill the personal balanced-HRV band from computed baselines when
        # Garmin's own baseline wasn't synced, so the chart band always shows.
        full = db.get_all(conn)
        for row in rows:
            if row.get("hrv_balanced_low") is None or row.get("hrv_balanced_high") is None:
                b = metric_baseline(full, "hrv_last_night", row["date"])
                if b:
                    row["hrv_balanced_low"] = round(b["low"], 1)
                    row["hrv_balanced_high"] = round(b["high"], 1)
        return {"rows": rows}
    finally:
        conn.close()


@app.get("/api/trends")
def trends(granularity: str = "week"):
    if granularity not in ("week", "month"):
        return JSONResponse({"error": "granularity must be week or month"}, status_code=400)
    conn = _conn()
    try:
        return build_trends(db.get_all(conn), granularity)
    finally:
        conn.close()


@app.get("/api/correlations")
def correlations():
    conn = _conn()
    try:
        return {"correlations": find_correlations(db.get_all(conn))}
    finally:
        conn.close()


# ---------------------------------------------------------------- sync (bg) --

class _SyncManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.state = "idle"          # idle / running / done / error
        self.message = ""

    def snapshot(self):
        return {"state": self.state, "message": self.message}

    def start(self, days: int) -> bool:
        with self._lock:
            if self.state == "running":
                return False
            self.state, self.message = "running", f"מסנכרן {days} ימים..."
        threading.Thread(target=self._run, args=(days,), daemon=True).start()
        return True

    def _run(self, days: int):
        from ..garmin_client import LoginRequired, client_from_tokens
        from ..sync import run_sync

        try:
            garmin = client_from_tokens()
            fetched = run_sync(days=days, garmin=garmin, db_path=_db_path())
            self.state = "done"
            self.message = f"סנכרון הושלם - נמשכו {fetched} ימים."
        except LoginRequired as exc:
            self.state, self.message = "error", str(exc)
        except Exception as exc:
            self.state, self.message = "error", f"שגיאת סנכרון: {exc}"


SYNC = _SyncManager()


class SyncRequest(BaseModel):
    days: int = 30


@app.post("/api/sync")
def start_sync(req: SyncRequest):
    if DEMO_MODE:
        return JSONResponse({"error": "מצב דמו - סנכרון כבוי. הרץ בלי --demo כדי למשוך נתונים אמיתיים."},
                            status_code=400)
    if not SYNC.start(max(1, min(req.days, 365))):
        return JSONResponse({"error": "סנכרון כבר רץ"}, status_code=409)
    return {"ok": True}


# --------------------------------------------------------------- login (bg) --

class _LoginManager:
    """Runs the Garmin login in a thread. If the account requires MFA, the
    prompt callback blocks on a queue until the user posts the code."""

    def __init__(self):
        self._lock = threading.Lock()
        self._mfa_queue: queue.Queue[str] = queue.Queue()
        self.state = "idle"          # idle / running / mfa_required / success / error
        self.message = ""

    def snapshot(self):
        return {"state": self.state, "message": self.message}

    def start(self, email: str, password: str) -> bool:
        with self._lock:
            if self.state in ("running", "mfa_required"):
                return False
            self.state, self.message = "running", "מתחבר לגרמין..."
        while not self._mfa_queue.empty():
            self._mfa_queue.get_nowait()
        threading.Thread(target=self._run, args=(email, password), daemon=True).start()
        return True

    def _prompt_mfa(self) -> str:
        self.state = "mfa_required"
        self.message = "נדרש קוד אימות (MFA) - בדוק את המייל/אפליקציה והזן את הקוד."
        try:
            code = self._mfa_queue.get(timeout=300)
        except queue.Empty:
            raise TimeoutError("לא הוזן קוד אימות בזמן")
        self.state, self.message = "running", "מאמת קוד..."
        return code

    def submit_mfa(self, code: str) -> bool:
        if self.state != "mfa_required":
            return False
        self._mfa_queue.put(code.strip())
        return True

    def _run(self, email: str, password: str):
        from ..garmin_client import login_with_credentials

        try:
            login_with_credentials(email, password, prompt_mfa=self._prompt_mfa)
            self.state = "success"
            self.message = "מחובר! ה-session נשמר מקומית - אפשר לסנכרן."
        except Exception as exc:
            self.state, self.message = "error", f"ההתחברות נכשלה: {exc}"


LOGIN = _LoginManager()


class LoginRequest(BaseModel):
    email: str
    password: str


class MfaRequest(BaseModel):
    code: str


@app.post("/api/login")
def start_login(req: LoginRequest):
    if DEMO_MODE:
        return JSONResponse({"error": "מצב דמו - התחברות כבויה."}, status_code=400)
    if not LOGIN.start(req.email, req.password):
        return JSONResponse({"error": "התחברות כבר בתהליך"}, status_code=409)
    return {"ok": True}


@app.post("/api/login/mfa")
def submit_mfa(req: MfaRequest):
    if not LOGIN.submit_mfa(req.code):
        return JSONResponse({"error": "אין בקשת MFA ממתינה"}, status_code=400)
    return {"ok": True}
