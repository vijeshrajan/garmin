"""Run a complete Garmin refresh and persist safe, user-visible status metadata."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "data" / "refresh_status.json"


def read_status() -> dict:
    try:
        value = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_status(value: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(STATUS_PATH)


parser = argparse.ArgumentParser()
parser.add_argument("--source", choices=("button", "manual", "scheduled"), default="manual")
args = parser.parse_args()
previous = read_status()
started = datetime.now().astimezone()
write_status({**previous, "state": "refreshing", "started_at": started.isoformat(), "source": args.source})
start_clock = time.monotonic()

pull = subprocess.run([sys.executable, str(ROOT / "pull.py")], cwd=ROOT)
if pull.returncode:
    write_status({**previous, "state": "failed", "last_error_at": datetime.now().astimezone().isoformat(), "source": args.source})
    raise SystemExit(pull.returncode)

completed = datetime.now().astimezone()
status = {
    "state": "success",
    "last_success": completed.isoformat(),
    "source": args.source,
    "duration_seconds": round(time.monotonic() - start_clock, 1),
}
write_status(status)
build = subprocess.run([sys.executable, str(ROOT / "build.py")], cwd=ROOT)
if build.returncode:
    write_status({**status, "state": "failed", "last_error_at": datetime.now().astimezone().isoformat()})
    raise SystemExit(build.returncode)
print(f"Refresh completed at {completed:%d %b %Y, %I:%M:%S %p}")

