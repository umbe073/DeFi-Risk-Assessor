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

echo "[smoke] checking hardcoded local-machine leftovers (excluding archive/ and this script)"
# Use find+grep so archive/obsolete_scripts and this file are always skipped (ripgrep multi-glob
# excludes are brittle across versions and can still scan archive/).
# Do not match /opt/.../scripts/v2.0 (legitimate server fallbacks) or /home/runner/... checkouts.
pattern='/Users/[^[:space:]]*scripts/v2\.(0|8)|/venv/data/risk_reports|/venv/data/social_reports'
found=0
while IFS= read -r -d '' f; do
  if grep -qE "${pattern}" "$f" 2>/dev/null; then
    grep -nE "${pattern}" "$f" >&2 || true
    found=1
  fi
done < <(find "${V2_DIR}" -type f \
  ! -path '*/archive/*' \
  ! -path '*/ci/verify_v2_8_smoke.sh' \
  \( -name '*.py' -o -name '*.sh' -o -name '*.md' -o -name '*.command' -o -name '*.plist' \
     -o -name '*.yml' -o -name '*.yaml' -o -name '*.json' \) -print0)
if [[ "${found}" -ne 0 ]]; then
  echo "[smoke] found legacy hardcoded path(s), review before deploy" >&2
  exit 1
fi

echo "[smoke] health probes (best-effort)"
curl -sS -m 5 "http://127.0.0.1/healthz" >/dev/null || true
curl -sS -m 5 "http://127.0.0.1:5001/webhook/health/deep/polygon" >/dev/null || true

echo "[smoke] ok"
