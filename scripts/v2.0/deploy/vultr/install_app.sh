#!/usr/bin/env bash
set -euo pipefail

# Prepare python environment and dependencies.
# Run as root after code is present at /opt/defi-risk/app

APP_USER="defirisk"
APP_HOME="/opt/defi-risk"
APP_REPO_DIR="${APP_HOME}/app"
VENV_DIR="${APP_HOME}/venv"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

if [[ ! -d "${APP_REPO_DIR}" ]]; then
  echo "Missing ${APP_REPO_DIR}. Upload/copy the repository first."
  exit 1
fi

echo "Ensuring ownership..."
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}"

echo "Creating virtualenv and installing dependencies..."
sudo -u "${APP_USER}" bash -lc "
set -euo pipefail
python3 -m venv '${VENV_DIR}'
source '${VENV_DIR}/bin/activate'
pip install --upgrade pip wheel setuptools
# Linux server install: exclude desktop macOS-only packages.
awk '
/^pyobjc-core==/ {next}
/^pyobjc-framework-Cocoa==/ {next}
/^pyobjc-framework-Quartz==/ {next}
/^pystray==/ {next}
/^tkinter-tooltip/ {next}
{print}
' '${APP_REPO_DIR}/requirements.txt' > /tmp/requirements.server.txt
pip install -r /tmp/requirements.server.txt
pip install gunicorn
"

echo "Application dependencies installed."
