"""API smoke tests against a seeded demo database (no Garmin access)."""

from fastapi.testclient import TestClient

from garmin_analyzer.config import DEMO_DB_PATH
from garmin_analyzer.demo import seed
from garmin_analyzer.web.main import app

client = TestClient(app)
seed(DEMO_DB_PATH, days=60)


def test_status():
    res = client.get("/api/status").json()
    assert res["demo"] is True
    assert res["days"] == 60


def test_today_insight():
    res = client.get("/api/today").json()
    assert res["insight"] is not None
    assert res["insight"]["status"] in ("ready", "moderate", "rest", "no_data")
    assert res["day"]["sleep_score"] is not None


def test_history():
    rows = client.get("/api/history?days=14").json()["rows"]
    assert len(rows) == 14
    assert rows[0]["date"] < rows[-1]["date"]


def test_trends():
    res = client.get("/api/trends?granularity=week").json()
    assert res["granularity"] == "week"
    assert len(res["periods"]) >= 8
    assert client.get("/api/trends?granularity=bogus").status_code == 400


def test_correlations_found_in_demo_data():
    res = client.get("/api/correlations").json()
    # Demo data embeds real relationships, so at least one should surface
    assert len(res["correlations"]) >= 1


def test_sync_blocked_in_demo():
    assert client.post("/api/sync", json={"days": 7}).status_code == 400


def test_index_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "Garmin Metrics Analyzer" in res.text
