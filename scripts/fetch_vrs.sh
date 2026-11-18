#!/usr/bin/env bash
# Download Valve's VRS repository at a pinned commit into data/raw/vrs.
# Pinning keeps every result reproducible; bump VRS_COMMIT to use newer data
# (and note the change in docs/JOURNAL.md).
set -euo pipefail
VRS_COMMIT="${VRS_COMMIT:-f8c55f250fdef796d708aa32814587932154fa04}"  # 2026-11-02 standings
DEST="$(cd "$(dirname "$0")/.." && pwd)/data/raw/vrs"
mkdir -p "$DEST"
cd "$DEST"
[ -d .git ] || git init -q
git remote get-url origin >/dev/null 2>&1 || git remote add origin https://github.com/ValveSoftware/counter-strike_regional_standings
git fetch -q --depth 1 origin "$VRS_COMMIT"
git checkout -q --detach FETCH_HEAD
echo "VRS data at $(git rev-parse --short HEAD) in $DEST"
