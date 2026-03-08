#!/usr/bin/env bash
set -euo pipefail

STRICT=false
RUN_SERVICES=false
JOURNAL_LINES=12

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=true
      shift
      ;;
    --run-services)
      RUN_SERVICES=true
      shift
      ;;
    --journal-lines)
      JOURNAL_LINES="${2:-12}"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: verify_deploy_packs.sh [--strict] [--run-services] [--journal-lines N]

Checks rollout health for deploy-pack timers/services:
  - script-api-watchdog
  - risk-worker
  - status-sampler
  - support-resend-sync
  - cloudflare-ufw-sync
  - crowdsec-slack-alerts
  - uptimerobot-slack-relay
  - user-telemetry-retention

Options:
  --strict         Exit non-zero on warnings in addition to failures.
  --run-services   Trigger each service once via systemctl start before status read.
  --journal-lines  Number of recent log lines to print per service (default: 12).
USAGE
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found; run this on a systemd host." >&2
  exit 2
fi

if ! [[ "${JOURNAL_LINES}" =~ ^[0-9]+$ ]]; then
  echo "--journal-lines must be an integer." >&2
  exit 2
fi

if ! command -v journalctl >/dev/null 2>&1; then
  echo "journalctl not found; run this on a systemd host." >&2
  exit 2
fi

readonly PACKS=(
  "script-api-watchdog.timer|script-api-watchdog.service|Script API watchdog"
  "risk-worker.timer|risk-worker.service|Risk worker"
  "status-sampler.timer|status-sampler.service|Services Status sampler"
  "support-resend-sync.timer|support-resend-sync.service|Resend fallback sync"
  "cloudflare-ufw-sync.timer|cloudflare-ufw-sync.service|Cloudflare UFW sync"
  "crowdsec-slack-alerts.timer|crowdsec-slack-alerts.service|CrowdSec Slack relay"
  "uptimerobot-slack-relay.timer|uptimerobot-slack-relay.service|UptimeRobot Slack relay"
  "user-telemetry-retention.timer|user-telemetry-retention.service|User telemetry retention"
)

warn_count=0
fail_count=0

_show_prop() {
  local unit="$1"
  local prop="$2"
  systemctl show "${unit}" -p "${prop}" --value 2>/dev/null || true
}

_unit_exists() {
  local unit="$1"
  local load_state
  load_state="$(_show_prop "${unit}" "LoadState")"
  [[ "${load_state}" == "loaded" ]]
}

_print_result() {
  local level="$1"
  local label="$2"
  local message="$3"
  printf '%-5s %-34s %s\n' "${level}" "${label}" "${message}"
}

echo "Deploy pack rollout verification"
echo "Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo

for row in "${PACKS[@]}"; do
  IFS='|' read -r timer_unit service_unit label <<<"${row}"
  echo "== ${label} =="

  timer_exists=true
  service_exists=true
  if ! _unit_exists "${timer_unit}"; then
    timer_exists=false
    _print_result "FAIL" "${timer_unit}" "unit not loaded"
    fail_count=$((fail_count + 1))
  fi
  if ! _unit_exists "${service_unit}"; then
    service_exists=false
    _print_result "FAIL" "${service_unit}" "unit not loaded"
    fail_count=$((fail_count + 1))
  fi
  if [[ "${timer_exists}" == "false" || "${service_exists}" == "false" ]]; then
    echo
    continue
  fi

  timer_enabled="$(systemctl is-enabled "${timer_unit}" 2>/dev/null || true)"
  timer_active="$(_show_prop "${timer_unit}" "ActiveState")"
  timer_next="$(_show_prop "${timer_unit}" "NextElapseUSecRealtime")"
  timer_last="$(_show_prop "${timer_unit}" "LastTriggerUSec")"
  if [[ "${timer_enabled}" == "enabled" ]]; then
    _print_result "PASS" "${timer_unit}" "enabled"
  else
    _print_result "WARN" "${timer_unit}" "is-enabled=${timer_enabled:-unknown}"
    warn_count=$((warn_count + 1))
  fi
  if [[ "${timer_active}" == "active" ]]; then
    _print_result "PASS" "${timer_unit}" "active"
  else
    _print_result "WARN" "${timer_unit}" "ActiveState=${timer_active:-unknown}"
    warn_count=$((warn_count + 1))
  fi
  _print_result "INFO" "${timer_unit}" "Next=${timer_next:-n/a} Last=${timer_last:-n/a}"

  if [[ "${RUN_SERVICES}" == "true" ]]; then
    if systemctl start "${service_unit}" >/dev/null 2>&1; then
      _print_result "INFO" "${service_unit}" "manually started for verification"
    else
      _print_result "WARN" "${service_unit}" "manual start returned non-zero"
      warn_count=$((warn_count + 1))
    fi
  fi

  service_result="$(_show_prop "${service_unit}" "Result")"
  service_active="$(_show_prop "${service_unit}" "ActiveState")"
  service_exec_status="$(_show_prop "${service_unit}" "ExecMainStatus")"
  service_last_start="$(_show_prop "${service_unit}" "ExecMainStartTimestamp")"
  service_last_end="$(_show_prop "${service_unit}" "ExecMainExitTimestamp")"

  if [[ "${service_result}" == "success" || -z "${service_result}" ]]; then
    _print_result "PASS" "${service_unit}" "Result=${service_result:-unknown}"
  else
    _print_result "WARN" "${service_unit}" "Result=${service_result}"
    warn_count=$((warn_count + 1))
  fi
  _print_result "INFO" "${service_unit}" "ActiveState=${service_active:-unknown} ExecMainStatus=${service_exec_status:-n/a}"
  _print_result "INFO" "${service_unit}" "Start=${service_last_start:-n/a} End=${service_last_end:-n/a}"

  echo "-- ${service_unit} recent logs (${JOURNAL_LINES}) --"
  journalctl -u "${service_unit}" --no-pager -n "${JOURNAL_LINES}" || true
  echo
done

echo "Summary: fail=${fail_count} warn=${warn_count}"
if (( fail_count > 0 )); then
  exit 1
fi
if [[ "${STRICT}" == "true" ]] && (( warn_count > 0 )); then
  exit 1
fi
exit 0
