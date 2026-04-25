#!/usr/bin/env bash
set -euo pipefail

echo "== Runtime discovery =="
echo "[host] $(hostname)"
echo "[user] $(id -un)"
echo "[pwd]  $(pwd)"
echo

echo "== /opt layout =="
ls -la /opt || true
echo

echo "== Relevant systemd units =="
systemctl list-units --type=service --all | rg "defirisk-webhook|hodler-script-api|hodler-web-portal|risk-worker|status-sampler" || true
echo

show_unit() {
  local unit="$1"
  echo "-- ${unit} --"
  systemctl show "${unit}" -p WorkingDirectory -p ExecStart -p EnvironmentFile -p User --value 2>/dev/null || true
  echo
}

show_unit "defirisk-webhook.service"
show_unit "hodler-script-api.service"
show_unit "hodler-web-portal.service"

echo "== Listening ports =="
ss -lntp | rg ":5001|:5050|:80|:443" || true
echo

echo "== Local health probes =="
echo "-- http://127.0.0.1/healthz --"
curl -sS -m 5 "http://127.0.0.1/healthz" || true
echo
echo "-- http://127.0.0.1:5001/webhook/health/deep/polygon --"
curl -sS -m 5 "http://127.0.0.1:5001/webhook/health/deep/polygon" || true
echo

echo "== Suggested canonical root guess =="
if [[ -d "/opt/defi-risk/app/scripts/v2.0" ]]; then
  echo "/opt/defi-risk/app"
elif [[ -d "/opt/hodler-suite/scripts/v2.0" ]]; then
  echo "/opt/hodler-suite"
else
  echo "unknown (inspect WorkingDirectory values above)"
fi
