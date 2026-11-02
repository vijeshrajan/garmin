"""Cloudflare Pages build entry point.

Runs the same Garmin pull and dashboard generator used locally, then packages the
result as an advanced-mode Pages Function in ``dist/_worker.js``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

os.environ.setdefault("TZ", "Asia/Kolkata")
if hasattr(__import__("time"), "tzset"):
    __import__("time").tzset()

subprocess.run(
    [sys.executable, str(ROOT / "refresh_runner.py"), "--source", "scheduled"],
    cwd=ROOT,
    check=True,
)
subprocess.run([sys.executable, str(ROOT / "build_cloudflare_worker.py")], cwd=ROOT, check=True)

DIST.mkdir(parents=True, exist_ok=True)
shutil.copyfile(ROOT / "data" / "cloudflare_worker.js", DIST / "_worker.js")
print(f"Cloudflare Pages output ready: {DIST}")

