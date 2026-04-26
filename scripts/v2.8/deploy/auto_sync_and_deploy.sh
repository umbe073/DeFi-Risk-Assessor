#!/usr/bin/env bash
set -euo pipefail

# GitHub-triggered server deploy for v2.8-only scope.
# Requires:
# - git available on the host; APP_ROOT may be a first-time/non-git directory
# - service names set correctly for the host
# - health endpoints reachable locally

APP_ROOT="${APP_ROOT:-/opt/hodler-suite}"
REPO_URL="${REPO_URL:-https://github.com/ddos-revenge/DeFi-Risk-Assessor.git}"
BRANCH="${BRANCH:-main}"
BACKUP_ROOT="${BACKUP_ROOT:-${APP_ROOT}/backups/auto_deploy}"
RUNTIME_TARGET_DIR="${RUNTIME_TARGET_DIR:-${APP_ROOT}/scripts/v2.0}"
SOURCE_DIR="${SOURCE_DIR:-${APP_ROOT}/scripts/v2.8}"
HEALTH_URL_APP="${HEALTH_URL_APP:-http://127.0.0.1/healthz}"
HEALTH_URL_SCRIPT="${HEALTH_URL_SCRIPT:-http://127.0.0.1:5001/webhook/health/deep/polygon}"
WEB_SERVICE="${WEB_SERVICE:-hodler-web-portal.service}"
SCRIPT_SERVICE="${SCRIPT_SERVICE:-defirisk-webhook.service}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SNAPSHOT_DIR="${BACKUP_ROOT}/${STAMP}"
PREV_COMMIT_FILE="${SNAPSHOT_DIR}/previous_commit.txt"

mkdir -p "${SNAPSHOT_DIR}"

mkdir -p "${APP_ROOT}"
cd "${APP_ROOT}"
APP_ROOT="$(pwd -P)"
SOURCE_DIR="${SOURCE_DIR%/}"
RUNTIME_TARGET_DIR="${RUNTIME_TARGET_DIR%/}"
if [[ "${RUNTIME_TARGET_DIR}" == "${APP_ROOT}" ]]; then
  echo "[deploy] WARNING: runtime target was APP_ROOT; using ${APP_ROOT}/scripts/v2.0 instead"
  RUNTIME_TARGET_DIR="${APP_ROOT}/scripts/v2.0"
fi
if [[ "${RUNTIME_TARGET_DIR}" == "${SOURCE_DIR}" ||
      "${SOURCE_DIR}" == "${RUNTIME_TARGET_DIR}/"* ||
      "${RUNTIME_TARGET_DIR}" == "${SOURCE_DIR}/"* ]]; then
  echo "[deploy] unsafe paths: source (${SOURCE_DIR}) and runtime target (${RUNTIME_TARGET_DIR}) overlap" >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[deploy] APP_ROOT is not a git checkout; initializing repository at ${APP_ROOT}"
  git init
fi
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "${REPO_URL}"
else
  git remote add origin "${REPO_URL}"
fi

PREV_COMMIT=""
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  PREV_COMMIT="$(git rev-parse HEAD)"
fi
echo "${PREV_COMMIT}" > "${PREV_COMMIT_FILE}"
echo "[deploy] previous commit: ${PREV_COMMIT:-<none>}"
echo "[deploy] source dir: ${SOURCE_DIR}"
echo "[deploy] runtime target: ${RUNTIME_TARGET_DIR}"

echo "[deploy] creating scoped backup"
mkdir -p "${SNAPSHOT_DIR}/runtime-target"
if [[ -d "${RUNTIME_TARGET_DIR}" ]]; then
  rsync -a \
    --exclude ".git/" \
    --exclude ".venv/" \
    "${RUNTIME_TARGET_DIR}/" "${SNAPSHOT_DIR}/runtime-target/"
else
  echo "[deploy] runtime target does not exist yet; backup is empty"
fi

if [[ -f "${APP_ROOT}/scripts/v2.8/deploy/runtime_discovery.sh" ]]; then
  bash "${APP_ROOT}/scripts/v2.8/deploy/runtime_discovery.sh" > "${SNAPSHOT_DIR}/runtime_discovery.txt" 2>&1 || true
fi

echo "[deploy] syncing from origin/${BRANCH}"
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"

if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "[deploy] missing source dir: ${SOURCE_DIR}" >&2
  exit 1
fi
mkdir -p "${RUNTIME_TARGET_DIR}"
echo "[deploy] syncing source -> runtime target"
rsync -a --delete \
  --exclude ".git/" \
  --exclude ".venv/" \
  --exclude ".env" \
  --exclude "web_portal.env" \
  --exclude "data/" \
  "${SOURCE_DIR}/" "${RUNTIME_TARGET_DIR}/"

echo "[deploy] restarting services"
sudo systemctl restart "${WEB_SERVICE}" || true
sudo systemctl restart "${SCRIPT_SERVICE}" || true

sleep 4
echo "[deploy] health checks"
set +e
curl -fsS -m 10 "${HEALTH_URL_APP}" >/dev/null
APP_OK=$?
curl -fsS -m 10 "${HEALTH_URL_SCRIPT}" >/dev/null
SCRIPT_OK=$?
set -e

if [[ ${APP_OK} -ne 0 || ${SCRIPT_OK} -ne 0 ]]; then
  echo "[deploy] health check failed, rolling back"
  if [[ -n "${PREV_COMMIT}" ]]; then
    git reset --hard "${PREV_COMMIT}"
  else
    echo "[deploy] no previous git commit to restore"
  fi
  rsync -a --delete "${SNAPSHOT_DIR}/runtime-target/" "${RUNTIME_TARGET_DIR}/"
  sudo systemctl restart "${WEB_SERVICE}" || true
  sudo systemctl restart "${SCRIPT_SERVICE}" || true
  exit 1
fi

echo "[deploy] success"
