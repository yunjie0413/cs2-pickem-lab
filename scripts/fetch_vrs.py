"""Download Valve's VRS repository at a pinned commit into data/raw/vrs.

Pinning keeps every result reproducible. To use newer data, change
VRS_COMMIT (or pass --commit) and note the change in docs/JOURNAL.md.

Usage:
    python scripts/fetch_vrs.py
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

VRS_COMMIT = "f8c55f250fdef796d708aa32814587932154fa04"  # 2026-11-02 standings
URL = "https://github.com/ValveSoftware/counter-strike_regional_standings"
ROOT = Path(__file__).resolve().parents[1]


def git(dest: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=dest, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", default=VRS_COMMIT)
    args = ap.parse_args()

    dest = ROOT / "data" / "raw" / "vrs"
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / ".git").exists():
        git(dest, "init", "-q")
        git(dest, "remote", "add", "origin", URL)
        git(dest, "config", "core.longpaths", "true")  # Windows: allow paths over 260 characters
    git(dest, "fetch", "-q", "--depth", "1", "origin", args.commit)
    git(dest, "checkout", "-q", "--detach", "FETCH_HEAD")
    print(f"VRS data at {git(dest, 'rev-parse', '--short', 'HEAD')} in {dest}")


if __name__ == "__main__":
    main()
