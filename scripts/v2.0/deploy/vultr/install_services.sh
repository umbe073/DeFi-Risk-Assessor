#!/usr/bin/env bash
set -euo pipefail

# Install systemd + nginx configs from this deploy folder.
# Run as root from repo path.

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install -m 0644 "${SCRIPT_DIR}/defirisk-webhook.service" /etc/systemd/system/defirisk-webhook.service
install -m 0644 "${SCRIPT_DIR}/defirisk-webportal.service" /etc/systemd/system/defirisk-webportal.service
install -m 0644 "${SCRIPT_DIR}/nginx-defirisk.conf" /etc/nginx/sites-available/defirisk

ln -sf /etc/nginx/sites-available/defirisk /etc/nginx/sites-enabled/defirisk
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl daemon-reload
systemctl enable defirisk-webhook
systemctl enable defirisk-webportal
systemctl restart defirisk-webhook
systemctl restart defirisk-webportal
systemctl restart nginx

echo "Services installed."
systemctl --no-pager --full status defirisk-webhook | sed -n '1,15p'
systemctl --no-pager --full status defirisk-webportal | sed -n '1,15p'
