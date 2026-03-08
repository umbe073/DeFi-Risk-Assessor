#!/usr/bin/env bash
set -euo pipefail

# Safe web_portal deployment helper.
# Preserves server runtime state by excluding local/deployed virtualenv, env files, and DB data.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_WEB_PORTAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST="${1:-linuxuser@80.240.31.172}"
REMOTE_TMP_DIR="${2:-/tmp/hodler-suite-web-portal/}"
REMOTE_APP_DIR="${3:-/opt/hodler-suite/web_portal/}"
SERVICE_NAME="${4:-hodler-web-portal.service}"

echo "Deploy target:"
echo "  host=${HOST}"
echo "  local=${LOCAL_WEB_PORTAL_DIR}/"
echo "  remote_tmp=${REMOTE_TMP_DIR}"
echo "  remote_app=${REMOTE_APP_DIR}"
echo "  service=${SERVICE_NAME}"

rsync -az --delete \
  --exclude ".git/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".venv/" \
  --exclude ".env" \
  --exclude "web_portal.env" \
  --exclude "data/" \
  "${LOCAL_WEB_PORTAL_DIR}/" "${HOST}:${REMOTE_TMP_DIR}"

ssh "${HOST}" "set -euo pipefail
sudo install -d -m 0755 '${REMOTE_APP_DIR}'
sudo rsync -a --delete \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude 'web_portal.env' \
  --exclude 'data/' \
  '${REMOTE_TMP_DIR}' '${REMOTE_APP_DIR}'
sudo systemctl restart '${SERVICE_NAME}'
sudo systemctl status --no-pager '${SERVICE_NAME}'
"
