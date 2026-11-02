"""Small read-only client for Garmin's official Personal API."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR / ".env.local"
DATA_DIR = PROJECT_DIR / "data"
TOKEN_PATH = DATA_DIR / "access_token.json"
BASE_URL = "https://personal.connectapi.garmin.com"
TOKEN_URL = (
    BASE_URL
    + "/personalapitoken-service/personal-api/personal-api-key/token"
)
TOKEN_MAX_AGE_SECONDS = 20 * 60 * 60


class GarminError(RuntimeError):
    """A safe-to-display Garmin API error that never contains credentials."""


class GarminHTTPError(GarminError):
    def __init__(self, status: int, message: str | None = None):
        self.status = status
        super().__init__(message or f"Garmin data request failed (HTTP {status}).")


def load_api_key() -> str:
    environment_key = os.environ.get("GARMIN_PERSONAL_API_KEY", "").strip()
    if environment_key:
        return environment_key
    if not ENV_PATH.exists():
        raise GarminError("The API key file is missing.")

    for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("GARMIN_PERSONAL_API_KEY="):
            key = line.partition("=")[2].strip()
            if key:
                return key
            break
    raise GarminError("The API key is not set.")


def _cached_token() -> str | None:
    try:
        cached = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        created_at = float(cached["created_at"])
        token = str(cached["access_token"]).strip()
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if token and time.time() - created_at < TOKEN_MAX_AGE_SECONDS:
        return token
    return None


def get_access_token() -> str:
    token = _cached_token()
    if token:
        return token

    api_key = load_api_key()
    request = urllib.request.Request(
        TOKEN_URL,
        data=b"",
        method="POST",
        headers={
            "Authorization": f"ApiKey {api_key}",
            "User-Agent": "garmin-dashboard/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            token = response.read().decode("utf-8").strip()
    except urllib.error.HTTPError as exc:
        raise GarminError(
            f"Garmin rejected the token request (HTTP {exc.code})."
        ) from None
    except urllib.error.URLError as exc:
        raise GarminError("Could not reach Garmin's Personal API.") from None

    if not token:
        raise GarminError("Garmin returned an empty access token.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(
        json.dumps({"access_token": token, "created_at": time.time()}),
        encoding="utf-8",
    )
    return token


def get_json(path: str, retries: int = 4):
    token = get_access_token()
    refreshed_token = False

    for attempt in range(retries + 1):
        request = urllib.request.Request(
            BASE_URL + path,
            method="GET",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "garmin-dashboard/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and not refreshed_token:
                TOKEN_PATH.unlink(missing_ok=True)
                token = get_access_token()
                refreshed_token = True
                continue
            if exc.code in {429, 502, 503} and attempt < retries:
                wait_seconds = min(3 * (attempt + 1), 12)
                print(f"  Garmin is busy (HTTP {exc.code}); retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            raise GarminHTTPError(exc.code) from None
        except urllib.error.URLError:
            if attempt < retries:
                wait_seconds = min(3 * (attempt + 1), 12)
                print(f"  Network interruption; retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue
            raise GarminError("Could not reach Garmin's Personal API.") from None
        except json.JSONDecodeError:
            raise GarminError("Garmin returned data in an unexpected format.") from None

    raise GarminError("Garmin request failed after several retries.")

