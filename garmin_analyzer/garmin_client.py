"""Garmin Connect client with local session-token persistence.

Session tokens are saved under ``data/tokens`` after the first login, so
subsequent runs reuse them instead of logging in again (avoids 429 blocks).
Tokens stay valid for months; only when they expire is a fresh login needed.

MFA is supported via a ``prompt_mfa`` callback: the CLI passes an
``input()``-based prompt, and the web UI passes a queue-backed callback.
"""

from __future__ import annotations

from typing import Callable

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .config import TOKEN_DIR, ensure_dirs


class LoginRequired(Exception):
    """Raised when no valid saved session exists and credentials are needed."""


def client_from_tokens() -> Garmin:
    """Resume a session from saved tokens. Raises LoginRequired if absent/expired."""
    ensure_dirs()
    try:
        garmin = Garmin()
        garmin.login(str(TOKEN_DIR))
        return garmin
    except (FileNotFoundError, GarminConnectAuthenticationError):
        raise LoginRequired("אין session שמור - נדרשת התחברות ראשונית לגרמין")
    except Exception as exc:  # garth raises its own error types for bad tokens
        raise LoginRequired(f"ה-session השמור אינו תקף ({type(exc).__name__}) - נדרשת התחברות מחדש")


def login_with_credentials(
    email: str,
    password: str,
    prompt_mfa: Callable[[], str] | None = None,
) -> Garmin:
    """Full login with email+password (and MFA callback if the account needs it).
    On success, tokens are dumped to TOKEN_DIR for future sessions."""
    ensure_dirs()
    kwargs = {"email": email, "password": password}
    if prompt_mfa is not None:
        kwargs["prompt_mfa"] = prompt_mfa
    garmin = Garmin(**kwargs)
    garmin.login()
    garmin.garth.dump(str(TOKEN_DIR))
    return garmin


def has_saved_tokens() -> bool:
    return TOKEN_DIR.exists() and any(TOKEN_DIR.iterdir())


def interactive_login() -> Garmin:
    """CLI login flow: prompts for credentials and, if needed, an MFA code."""
    import getpass

    print("התחברות ל-Garmin Connect (הפרטים לא נשמרים - רק ה-session)")
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")

    def _mfa() -> str:
        return input("קוד אימות (MFA) שנשלח אליך: ").strip()

    try:
        garmin = login_with_credentials(email, password, prompt_mfa=_mfa)
    except GarminConnectTooManyRequestsError:
        raise SystemExit("גרמין חסמו זמנית בגלל יותר מדי נסיונות (429) - נסה שוב בעוד כשעה")
    except (GarminConnectAuthenticationError, GarminConnectConnectionError) as exc:
        raise SystemExit(f"ההתחברות נכשלה: {exc}")
    print(f"מחובר! ה-session נשמר ב-{TOKEN_DIR} - לא יידרש לוגין נוסף בזמן הקרוב.")
    return garmin


def get_client() -> Garmin:
    """Preferred entry point: saved tokens first, interactive login as fallback."""
    try:
        return client_from_tokens()
    except LoginRequired:
        return interactive_login()
