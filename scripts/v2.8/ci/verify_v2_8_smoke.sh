#!/usr/bin/env bash
set -euo pipefail

# CI-safe smoke checks for scripts/v2.8 (no operational secrets).
# Kept under scripts/v2.8/ci/ because scripts/v2.8/deploy is private/manual-only.

ROOT_DIR="${1:-/opt/hodler-suite}"
V2_DIR="${ROOT_DIR}/scripts/v2.8"

echo "[smoke] root=${ROOT_DIR}"
echo "[smoke] v2_dir=${V2_DIR}"

if [[ ! -d "${V2_DIR}" ]]; then
  echo "[smoke] missing ${V2_DIR}" >&2
  exit 1
fi

echo "[smoke] checking required dirs"
test -d "${V2_DIR}/data/risk_reports"
test -d "${V2_DIR}/data/social_reports"

echo "[smoke] compiling python files"
if rg --files "${V2_DIR}" -g "*.py" >/dev/null 2>&1; then
  python3 -m compileall -q "${V2_DIR}"
else
  echo "[smoke] no python files under ${V2_DIR} yet"
fi

echo "[smoke] checking hardcoded v2.0 leftovers"
if rg -n "/scripts/v2\\.0|/venv/data/risk_reports|/venv/data/social_reports" "${V2_DIR}" >/dev/null 2>&1; then
  echo "[smoke] found legacy hardcoded path(s), review before deploy:" >&2
  rg -n "/scripts/v2\\.0|/venv/data/risk_reports|/venv/data/social_reports" "${V2_DIR}" || true
  exit 1
fi

echo "[smoke] health probes (best-effort)"
curl -sS -m 5 "http://127.0.0.1/healthz" >/dev/null || true
curl -sS -m 5 "http://127.0.0.1:5001/webhook/health/deep/polygon" >/dev/null || true

echo "[smoke] ok"
