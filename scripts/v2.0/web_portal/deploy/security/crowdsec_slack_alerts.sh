#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="/var/lib/crowdsec-slack"
STATE_FILE="${STATE_DIR}/last_alert_id"
WEBHOOK_URL="${CROWDSEC_SLACK_WEBHOOK_URL:-}"
MAX_ALERTS="${CROWDSEC_SLACK_MAX_ALERTS_PER_RUN:-10}"

if [[ -z "${WEBHOOK_URL}" ]]; then
  echo "CROWDSEC_SLACK_WEBHOOK_URL not set; skipping."
  exit 0
fi

mkdir -p "${STATE_DIR}"
chown root:root "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

ALERTS_FILE="$(mktemp /tmp/crowdsec-alerts.XXXXXX.json)"
trap 'rm -f "${ALERTS_FILE}"' EXIT
if ! cscli alerts list -o json >"${ALERTS_FILE}" 2>/dev/null; then
  echo '[]' >"${ALERTS_FILE}"
fi

python3 - "${STATE_FILE}" "${WEBHOOK_URL}" "${MAX_ALERTS}" "${ALERTS_FILE}" <<'PY'
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

state_file = pathlib.Path(sys.argv[1])
webhook_url = sys.argv[2]
max_alerts = max(1, int(sys.argv[3]))
alerts_file = pathlib.Path(sys.argv[4])

try:
    last_id = int(state_file.read_text().strip())
except Exception:
    last_id = 0

try:
    payload = json.loads(alerts_file.read_text(encoding="utf-8"))
except Exception:
    payload = []

if not isinstance(payload, list):
    payload = []

def as_int(value: object) -> int:
    try:
        return int(str(value))
    except Exception:
        return 0

new_alerts = [item for item in payload if isinstance(item, dict) and as_int(item.get("id")) > last_id]
if not new_alerts:
    print("no_new_alerts")
    sys.exit(0)

new_alerts.sort(key=lambda item: as_int(item.get("id")))
selected = new_alerts[:max_alerts]

lines: list[str] = []
max_seen = last_id
for alert in selected:
    alert_id = as_int(alert.get("id"))
    if alert_id > max_seen:
        max_seen = alert_id
    scenario = str(alert.get("scenario") or "unknown_scenario").strip()
    source_ip = str(alert.get("source", {}).get("ip") if isinstance(alert.get("source"), dict) else "").strip()
    country = str(alert.get("source", {}).get("cn") if isinstance(alert.get("source"), dict) else "").strip()
    created = str(alert.get("created_at") or "").strip()
    line = f"• #{alert_id} `{scenario}`"
    if source_ip:
        line += f" from `{source_ip}`"
    if country:
        line += f" ({country})"
    if created:
        line += f" at {created}"
    lines.append(line)

if len(new_alerts) > len(selected):
    lines.append(f"… and {len(new_alerts) - len(selected)} more new alert(s).")

message = {
    "text": "*CrowdSec Alert Digest (Hodler Suite)*\n" + "\n".join(lines)
}

data = json.dumps(message).encode("utf-8")
req = urllib.request.Request(
    webhook_url,
    data=data,
    method="POST",
    headers={
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "HodlerSuiteCrowdSecSlack/1.0",
    },
)

with urllib.request.urlopen(req, timeout=10) as response:
    status = int(getattr(response, "status", 0) or 0)
    if status < 200 or status >= 300:
        raise RuntimeError(f"slack_http_{status}")

state_file.write_text(str(max_seen))
state_file.chmod(0o600)
print(f"sent_alerts={len(selected)} last_id={max_seen}")
PY
