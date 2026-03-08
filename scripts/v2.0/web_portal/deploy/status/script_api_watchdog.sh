#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${SCRIPT_API_WATCHDOG_ENV_FILE:-/opt/hodler-suite/web_portal/web_portal.env}"
HEALTH_URL_DEFAULT="http://127.0.0.1:5001/webhook/health"
TIMEOUT_DEFAULT="6"
FAILURE_THRESHOLD_DEFAULT="3"
HTTP_ATTEMPTS_DEFAULT="3"
RETRY_DELAY_DEFAULT="2"
STATE_FILE_DEFAULT="/var/lib/hodler-suite/script_api_watchdog.state"
UNIT_DEFAULT="hodler-script-api.service"

read_env_value() {
  local key="$1"
  awk -F= -v k="$key" '$1==k {print substr($0, index($0, $2)); found=1} END{if(!found) exit 1}' "${ENV_FILE}" 2>/dev/null | tail -n 1
}

strip_wrapping_quotes() {
  local val="$1"
  if [[ "${val}" == \"*\" && "${val}" == *\" ]]; then
    val="${val:1:${#val}-2}"
  elif [[ "${val}" == \'*\' && "${val}" == *\' ]]; then
    val="${val:1:${#val}-2}"
  fi
  printf "%s" "${val}"
}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[script-api-watchdog] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

health_url="$(strip_wrapping_quotes "$(read_env_value SCRIPT_API_WATCHDOG_URL || true)")"
timeout_raw="$(strip_wrapping_quotes "$(read_env_value SCRIPT_API_WATCHDOG_TIMEOUT_SECONDS || true)")"
failure_threshold_raw="$(strip_wrapping_quotes "$(read_env_value SCRIPT_API_WATCHDOG_FAILURE_THRESHOLD || true)")"
http_attempts_raw="$(strip_wrapping_quotes "$(read_env_value SCRIPT_API_WATCHDOG_HTTP_ATTEMPTS || true)")"
retry_delay_raw="$(strip_wrapping_quotes "$(read_env_value SCRIPT_API_WATCHDOG_RETRY_DELAY_SECONDS || true)")"
state_file="$(strip_wrapping_quotes "$(read_env_value SCRIPT_API_WATCHDOG_STATE_FILE || true)")"
systemd_unit="$(strip_wrapping_quotes "$(read_env_value SCRIPT_API_WATCHDOG_UNIT || true)")"

if [[ -z "${health_url}" ]]; then
  health_url="${HEALTH_URL_DEFAULT}"
fi
if [[ -z "${timeout_raw}" || ! "${timeout_raw}" =~ ^[0-9]+$ ]]; then
  timeout_raw="${TIMEOUT_DEFAULT}"
fi
if [[ -z "${failure_threshold_raw}" || ! "${failure_threshold_raw}" =~ ^[0-9]+$ ]]; then
  failure_threshold_raw="${FAILURE_THRESHOLD_DEFAULT}"
fi
if [[ -z "${http_attempts_raw}" || ! "${http_attempts_raw}" =~ ^[0-9]+$ ]]; then
  http_attempts_raw="${HTTP_ATTEMPTS_DEFAULT}"
fi
if [[ -z "${retry_delay_raw}" || ! "${retry_delay_raw}" =~ ^[0-9]+$ ]]; then
  retry_delay_raw="${RETRY_DELAY_DEFAULT}"
fi
if [[ -z "${state_file}" ]]; then
  state_file="${STATE_FILE_DEFAULT}"
fi
if [[ -z "${systemd_unit}" ]]; then
  systemd_unit="${UNIT_DEFAULT}"
fi

timeout_seconds=$((timeout_raw))
if (( timeout_seconds < 2 )); then
  timeout_seconds=2
elif (( timeout_seconds > 60 )); then
  timeout_seconds=60
fi

failure_threshold=$((failure_threshold_raw))
if (( failure_threshold < 1 )); then
  failure_threshold=1
elif (( failure_threshold > 30 )); then
  failure_threshold=30
fi

http_attempts=$((http_attempts_raw))
if (( http_attempts < 1 )); then
  http_attempts=1
elif (( http_attempts > 10 )); then
  http_attempts=10
fi

retry_delay_seconds=$((retry_delay_raw))
if (( retry_delay_seconds < 1 )); then
  retry_delay_seconds=1
elif (( retry_delay_seconds > 15 )); then
  retry_delay_seconds=15
fi

state_dir="$(dirname "${state_file}")"
install -d -m 0755 "${state_dir}"

failure_count=0
if [[ -f "${state_file}" ]]; then
  current="$(cat "${state_file}" 2>/dev/null || true)"
  if [[ "${current}" =~ ^[0-9]+$ ]]; then
    failure_count=$((current))
  fi
fi

body_file="$(mktemp /tmp/script-api-watchdog.XXXXXX.json)"
trap 'rm -f "${body_file}"' EXIT

http_code="000"
for attempt in $(seq 1 "${http_attempts}"); do
  http_code="$(
    curl -sS \
      --max-time "${timeout_seconds}" \
      -o "${body_file}" \
      -w "%{http_code}" \
      "${health_url}" \
    || true
  )"
  if [[ "${http_code}" =~ ^2[0-9][0-9]$ ]]; then
    break
  fi
  if (( attempt < http_attempts )); then
    sleep "${retry_delay_seconds}"
  fi
done

if [[ "${http_code}" =~ ^2[0-9][0-9]$ ]]; then
  printf "0" > "${state_file}"
  echo "[script-api-watchdog] ok unit=${systemd_unit} url=${health_url} http=${http_code} attempts=${http_attempts}"
  exit 0
fi

failure_count=$((failure_count + 1))
printf "%s" "${failure_count}" > "${state_file}"
echo "[script-api-watchdog] probe_failed unit=${systemd_unit} url=${health_url} http=${http_code:-000} failure_count=${failure_count}/${failure_threshold}" >&2

if (( failure_count < failure_threshold )); then
  exit 0
fi

if systemctl restart "${systemd_unit}" >/dev/null 2>&1; then
  printf "0" > "${state_file}"
  echo "[script-api-watchdog] restarted unit=${systemd_unit} after failure threshold breach"
  exit 0
fi

echo "[script-api-watchdog] restart_failed unit=${systemd_unit}" >&2
exit 1
