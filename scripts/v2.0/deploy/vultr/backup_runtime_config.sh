#!/usr/bin/env bash
set -euo pipefail

# Backup Nginx + env + systemd runtime config for rollback points.
# Run as root: sudo bash backup_runtime_config.sh

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/var/backups/defi-risk"
ARCHIVE="${BACKUP_DIR}/runtime-config-${STAMP}.tar.gz"
mkdir -p "${BACKUP_DIR}"

INCLUDE_PATHS=(
  /etc/nginx/sites-available/defirisk
  /etc/nginx/sites-enabled/defirisk
  /etc/defi-risk/web_portal.env
  /etc/defi-risk/webhook.env
  /etc/systemd/system/defirisk-webhook.service
  /etc/systemd/system/defirisk-webportal.service
)

EXISTING=()
for path in "${INCLUDE_PATHS[@]}"; do
  if [[ -e "$path" ]]; then
    EXISTING+=("$path")
  fi
done

if [[ ${#EXISTING[@]} -eq 0 ]]; then
  echo "No runtime config files found to back up."
  exit 1
fi

tar -czf "${ARCHIVE}" "${EXISTING[@]}"
chmod 600 "${ARCHIVE}"
sha256sum "${ARCHIVE}"

echo "Backup written to: ${ARCHIVE}"
echo "Stored files:"
for path in "${EXISTING[@]}"; do
  echo " - ${path}"
done
