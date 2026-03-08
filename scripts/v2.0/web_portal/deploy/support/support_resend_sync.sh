#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${SUPPORT_SYNC_ENV_FILE:-/opt/hodler-suite/web_portal/web_portal.env}"
BASE_URL_DEFAULT="http://127.0.0.1:5050"
LIMIT_DEFAULT="50"
TIMEOUT_SECONDS="${SUPPORT_SYNC_TIMEOUT_SECONDS:-25}"
WAIT_FOR_APP_SECONDS="${SUPPORT_SYNC_WAIT_FOR_APP_SECONDS:-20}"
HTTP_ATTEMPTS="${SUPPORT_SYNC_HTTP_ATTEMPTS:-3}"

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

to_bool() {
  case "$(printf "%s" "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[support-resend-sync] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

webhook_secret="$(strip_wrapping_quotes "$(read_env_value SUPPORT_INBOUND_WEBHOOK_SECRET || true)")"
routing_active_raw="$(strip_wrapping_quotes "$(read_env_value SUPPORT_INBOUND_ROUTING_ACTIVE || true)")"
base_url="$(strip_wrapping_quotes "$(read_env_value SUPPORT_RESEND_SYNC_BASE_URL || true)")"
limit_raw="$(strip_wrapping_quotes "$(read_env_value SUPPORT_RESEND_SYNC_LIMIT || true)")"

if ! to_bool "${routing_active_raw}"; then
  echo "[support-resend-sync] skipped (SUPPORT_INBOUND_ROUTING_ACTIVE is false)"
  exit 0
fi

if [[ -z "${webhook_secret}" ]]; then
  echo "[support-resend-sync] missing SUPPORT_INBOUND_WEBHOOK_SECRET" >&2
  exit 1
fi

if [[ -z "${base_url}" ]]; then
  base_url="${BASE_URL_DEFAULT}"
fi

if [[ -z "${limit_raw}" || ! "${limit_raw}" =~ ^[0-9]+$ ]]; then
  limit_raw="${LIMIT_DEFAULT}"
fi

if (( limit_raw < 1 )); then
  limit_raw=1
elif (( limit_raw > 100 )); then
  limit_raw=100
fi

sync_url="${base_url%/}/api/v1/support/inbound-email/resend/sync"
health_url="${base_url%/}/healthz"
body_file="$(mktemp /tmp/support-resend-sync.XXXXXX.json)"
trap 'rm -f "${body_file}"' EXIT

if [[ -z "${WAIT_FOR_APP_SECONDS}" || ! "${WAIT_FOR_APP_SECONDS}" =~ ^[0-9]+$ ]]; then
  WAIT_FOR_APP_SECONDS="20"
fi
if [[ -z "${HTTP_ATTEMPTS}" || ! "${HTTP_ATTEMPTS}" =~ ^[0-9]+$ ]]; then
  HTTP_ATTEMPTS="3"
fi
if (( HTTP_ATTEMPTS < 1 )); then
  HTTP_ATTEMPTS=1
fi

ready=0
for _ in $(seq 1 "${WAIT_FOR_APP_SECONDS}"); do
  if curl -fsS --max-time 3 "${health_url}" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if (( ready != 1 )); then
  echo "[support-resend-sync] app not ready url=${health_url}" >&2
  exit 1
fi

http_code=""
for attempt in $(seq 1 "${HTTP_ATTEMPTS}"); do
  http_code="$(
    curl -sS \
      --max-time "${TIMEOUT_SECONDS}" \
      -o "${body_file}" \
      -w "%{http_code}" \
      -X POST "${sync_url}" \
      -H "Content-Type: application/json" \
      -H "X-Support-Inbound-Secret: ${webhook_secret}" \
      -d "{\"limit\": ${limit_raw}}" || true
  )"
  if [[ "${http_code}" == "200" ]]; then
    break
  fi
  if (( attempt < HTTP_ATTEMPTS )); then
    sleep 1
  fi
done

if [[ "${http_code}" != "200" ]]; then
  echo "[support-resend-sync] failed http=${http_code} url=${sync_url}" >&2
  cat "${body_file}" >&2 || true
  exit 1
fi

python3 - "${body_file}" <<'PY'
from __future__ import annotations
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
policy = payload.get("policy", {}) if isinstance(payload.get("policy"), dict) else {}
print(
    "[support-resend-sync] ok"
    f" checked={int(payload.get('checked', 0) or 0)}"
    f" processed={int(payload.get('processed', 0) or 0)}"
    f" duplicates={int(payload.get('duplicates', 0) or 0)}"
    f" unmapped={int(payload.get('unmapped', 0) or 0)}"
    f" failed={int(payload.get('failed', 0) or 0)}"
    f" failed_total={int(payload.get('failed_total', payload.get('failed', 0)) or 0)}"
    f" breach={bool(policy.get('current_breach', False))}"
    f" sustained={bool(policy.get('sustained_breach', False))}"
)
PY
