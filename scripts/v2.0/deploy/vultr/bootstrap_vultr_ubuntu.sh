#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a fresh Ubuntu 24.04 Vultr instance for DeFi Risk services.
# Run as root: sudo bash bootstrap_vultr_ubuntu.sh

APP_USER="defirisk"
APP_GROUP="defirisk"
APP_HOME="/opt/defi-risk"
APP_LOG_DIR="/var/log/defi-risk"
APP_ETC_DIR="/etc/defi-risk"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

echo "[1/7] Updating base packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

echo "[2/7] Installing dependencies..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates \
  curl \
  git \
  nginx \
  ufw \
  fail2ban \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  libffi-dev \
  libssl-dev \
  pkg-config

echo "[3/7] Creating service user..."
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "${APP_HOME}" --shell /bin/bash "${APP_USER}"
fi

mkdir -p "${APP_HOME}" "${APP_LOG_DIR}" "${APP_ETC_DIR}"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_HOME}" "${APP_LOG_DIR}"
chmod 750 "${APP_ETC_DIR}"

echo "[4/7] Configuring firewall..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "[5/7] Enabling fail2ban + nginx..."
systemctl enable fail2ban
systemctl start fail2ban
systemctl enable nginx
systemctl start nginx

echo "[6/7] Creating env files if missing..."
if [[ ! -f "${APP_ETC_DIR}/webhook.env" ]]; then
  cat > "${APP_ETC_DIR}/webhook.env" <<'ENVEOF'
# Environment for webhook gunicorn service
PYTHONUNBUFFERED=1
PROJECT_ROOT=/opt/defi-risk/app
ENVEOF
fi

if [[ ! -f "${APP_ETC_DIR}/web_portal.env" ]]; then
  cat > "${APP_ETC_DIR}/web_portal.env" <<'ENVEOF'
# Environment for web portal gunicorn service
PYTHONUNBUFFERED=1
WEB_PORTAL_SECRET_KEY=change-this-before-public-launch
WEB_PORTAL_HOST=127.0.0.1
WEB_PORTAL_PORT=5050
WEB_PORTAL_FORCE_HTTPS=true
WEB_PORTAL_ALLOWED_ORIGINS=https://app.example.com
WEB_PORTAL_AUTH_DB=/opt/defi-risk/data/web_portal_auth.db
AUTH_2FA_ISSUER=Hodler Suite
MASTER_ACCOUNT_EMAIL=admin@hodler-suite.com
MASTER_ACCOUNT_PASSWORD=change-master-password-now
SESSION_IDLE_MINUTES=720
NOWPAYMENTS_ENABLED=false
NOWPAYMENTS_API_BASE=https://api.nowpayments.io/v1
NOWPAYMENTS_API_KEY=
NOWPAYMENTS_IPN_SECRET=
NOWPAYMENTS_SUCCESS_URL=https://app.example.com/account/subscription/success
NOWPAYMENTS_CANCEL_URL=https://app.example.com/account/subscription/cancel
SUPPORT_TRIAGE_PROVIDER=disabled
SUPPORT_TRIAGE_API_KEY=
SUPPORT_TRIAGE_WEBHOOK_URL=
SUPPORT_TRIAGE_WEBHOOK_SECRET=
ENVEOF
fi
chmod 640 "${APP_ETC_DIR}/webhook.env" "${APP_ETC_DIR}/web_portal.env"

echo "[7/7] Bootstrap complete."
echo
echo "Next steps:"
echo "1) Upload repository to ${APP_HOME}/app and chown to ${APP_USER}:${APP_GROUP}."
echo "2) Run install_app.sh as root (it switches to ${APP_USER})."
echo "3) Install systemd services + nginx config via install_services.sh."
