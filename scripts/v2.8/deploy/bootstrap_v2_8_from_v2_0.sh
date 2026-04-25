#!/usr/bin/env bash
set -euo pipefail

# One-time migration helper:
# - snapshots v2.8 (if present)
# - syncs scripts/v2.0 -> scripts/v2.8
# - excludes website subtree by default
# - rewrites hardcoded path strings to v2.8/data locations

ROOT_DIR="${1:-/opt/hodler-suite}"
INCLUDE_WEB_PORTAL="${INCLUDE_WEB_PORTAL:-false}"

SRC_DIR="${ROOT_DIR}/scripts/v2.0"
DST_DIR="${ROOT_DIR}/scripts/v2.8"
BACKUP_ROOT="${ROOT_DIR}/backups/v2_8_migration"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_ROOT}/v2.8-pre-migration-${STAMP}.tar.gz"

echo "[bootstrap] root=${ROOT_DIR}"
echo "[bootstrap] src=${SRC_DIR}"
echo "[bootstrap] dst=${DST_DIR}"
echo "[bootstrap] include_web_portal=${INCLUDE_WEB_PORTAL}"

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "[bootstrap] missing source directory: ${SRC_DIR}" >&2
  exit 1
fi

mkdir -p "${BACKUP_ROOT}"
if [[ -d "${DST_DIR}" ]]; then
  tar -C "${ROOT_DIR}/scripts" -czf "${BACKUP_FILE}" "v2.8"
  echo "[bootstrap] backup created: ${BACKUP_FILE}"
fi

RSYNC_EXCLUDES=(
  --exclude ".git/"
  --exclude "__pycache__/"
  --exclude "*.pyc"
  --exclude ".venv/"
  --exclude ".env"
  --exclude "web_portal.env"
  --exclude "data/"
)

if [[ "${INCLUDE_WEB_PORTAL}" != "true" ]]; then
  RSYNC_EXCLUDES+=(--exclude "web_portal/" --exclude "web_portal/**")
fi

mkdir -p "${DST_DIR}"
rsync -a --delete "${RSYNC_EXCLUDES[@]}" "${SRC_DIR}/" "${DST_DIR}/"

echo "[bootstrap] rewriting hardcoded path strings"
DST_DIR_ENV="${DST_DIR}" python3 - <<'PY'
from __future__ import annotations
import os
from pathlib import Path

root = Path(str(os.environ.get("DST_DIR_ENV", "")).strip())
if not root:
    raise SystemExit("DST_DIR_ENV is empty")
replacements = {
    "/scripts/v2.0": "/scripts/v2.8",
    "/venv/data/risk_reports": "/venv/scripts/v2.8/data/risk_reports",
    "/venv/data/social_reports": "/venv/scripts/v2.8/data/social_reports",
    "/data/risk_reports": "/scripts/v2.8/data/risk_reports",
    "/data/social_reports": "/scripts/v2.8/data/social_reports",
}

for py_file in root.rglob("*.py"):
    text = py_file.read_text(encoding="utf-8", errors="replace")
    updated = text
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != text:
        py_file.write_text(updated, encoding="utf-8")
PY

mkdir -p "${DST_DIR}/data/risk_reports" "${DST_DIR}/data/social_reports"
echo "[bootstrap] done"
echo "[bootstrap] next: run smoke checks from scripts/v2.8/deploy/verify_v2_8_smoke.sh"
