import os
import sys
import tempfile
from pathlib import Path

# Isolate all app data (DB, tokens) into a temp dir before any app import,
# and run the API in demo mode so no Garmin access is attempted.
_TMP = tempfile.mkdtemp(prefix="garmin_test_")
os.environ["GARMIN_ANALYZER_DATA"] = _TMP
os.environ["GARMIN_ANALYZER_DB"] = str(Path(_TMP) / "health.db")
os.environ["GARMIN_ANALYZER_TOKENS"] = str(Path(_TMP) / "tokens")
os.environ["GARMIN_ANALYZER_DEMO"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
