#!/usr/bin/env bash
set -euo pipefail

: "${UPTIMEROBOT_API_KEY:=}"
: "${UPTIMEROBOT_API_URL:=https://api.uptimerobot.com/v2/getMonitors}"
: "${UPTIMEROBOT_MONITOR_ID:=}"
: "${UPTIMEROBOT_TIMEOUT_SECONDS:=20}"
: "${UPTIMEROBOT_STATE_FILE:=/var/lib/hodler-suite/uptimerobot_slack_state.json}"
: "${SLACK_WEBHOOK_URL:=}"

if [[ -z "${UPTIMEROBOT_API_KEY}" ]]; then
  echo "[uptimerobot-slack-relay] UPTIMEROBOT_API_KEY missing; skipping."
  exit 0
fi
if [[ -z "${SLACK_WEBHOOK_URL}" ]]; then
  echo "[uptimerobot-slack-relay] SLACK_WEBHOOK_URL missing; skipping."
  exit 0
fi

STATE_DIR="$(dirname "${UPTIMEROBOT_STATE_FILE}")"
mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

TMP_JSON="$(mktemp /tmp/uptimerobot-monitor.XXXXXX.json)"
trap 'rm -f "${TMP_JSON}"' EXIT

REQUEST_BODY="api_key=${UPTIMEROBOT_API_KEY}&format=json&logs=1&logs_limit=1"
if [[ -n "${UPTIMEROBOT_MONITOR_ID}" ]]; then
  REQUEST_BODY="${REQUEST_BODY}&monitors=${UPTIMEROBOT_MONITOR_ID}"
fi

curl -fsS \
  --max-time "${UPTIMEROBOT_TIMEOUT_SECONDS}" \
  -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "${REQUEST_BODY}" \
  "${UPTIMEROBOT_API_URL}" \
  -o "${TMP_JSON}"

python3 - "${TMP_JSON}" "${UPTIMEROBOT_STATE_FILE}" "${SLACK_WEBHOOK_URL}" <<'PY'
import json
import pathlib
import sys
import urllib.request

payload_path = pathlib.Path(sys.argv[1])
state_path = pathlib.Path(sys.argv[2])
webhook_url = sys.argv[3]

status_labels = {
    "0": "paused",
    "1": "not checked yet",
    "2": "up",
    "8": "seems down",
    "9": "down",
}

raw = json.loads(payload_path.read_text(encoding="utf-8"))
if str(raw.get("stat", "")).strip().lower() != "ok":
    raise SystemExit(f"uptimerobot_api_not_ok: {raw}")

monitors = raw.get("monitors") or []
if not isinstance(monitors, list):
    monitors = []

state = {"monitors": {}}
if state_path.exists():
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("monitors"), dict):
            state = loaded
    except Exception:
        pass

known = state["monitors"]
changed = []
seeded = 0

for mon in monitors:
    if not isinstance(mon, dict):
        continue
    monitor_id = str(mon.get("id") or "").strip()
    if not monitor_id:
        continue

    status = str(mon.get("status") or "").strip()
    name = str(mon.get("friendly_name") or mon.get("url") or f"monitor-{monitor_id}").strip()
    url = str(mon.get("url") or "").strip()
    monitor_type = str(mon.get("type") or "").strip()

    previous = known.get(monitor_id)
    previous_status = ""
    if isinstance(previous, dict):
        previous_status = str(previous.get("status") or "").strip()

    if not previous_status:
        seeded += 1
    elif previous_status != status:
        changed.append(
            {
                "id": monitor_id,
                "name": name,
                "url": url,
                "old": previous_status,
                "new": status,
                "type": monitor_type,
            }
        )

    known[monitor_id] = {
        "status": status,
        "name": name,
        "url": url,
        "type": monitor_type,
    }

state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if not changed:
    print(f"uptimerobot_slack_relay: no_changes monitors={len(monitors)} seeded={seeded}")
    raise SystemExit(0)

for item in changed:
    old_label = status_labels.get(item["old"], item["old"] or "unknown")
    new_label = status_labels.get(item["new"], item["new"] or "unknown")
    headline = ":large_green_circle: Monitor recovered" if item["new"] == "2" else ":red_circle: Monitor degraded"
    text = (
        f"{headline}\n"
        f"*{item['name']}* (`{item['id']}`)\n"
        f"Status: `{old_label}` -> `{new_label}`\n"
        f"Type: `{item['type'] or 'n/a'}`"
    )
    if item["url"]:
        text += f"\nURL: {item['url']}"

    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
        if int(resp.status) >= 300:
            raise RuntimeError(f"slack_http_{resp.status}")

print(f"uptimerobot_slack_relay: posted={len(changed)} monitors={len(monitors)}")
PY
