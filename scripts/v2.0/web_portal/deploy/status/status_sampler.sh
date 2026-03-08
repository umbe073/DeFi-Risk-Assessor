#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${STATUS_SAMPLER_ENV_FILE:-/opt/hodler-suite/web_portal/web_portal.env}"
BASE_URL_DEFAULT="http://127.0.0.1:5050"
TIMEOUT_DEFAULT="20"
WAIT_FOR_APP_SECONDS="${STATUS_SAMPLER_WAIT_FOR_APP_SECONDS:-20}"
HTTP_ATTEMPTS="${STATUS_SAMPLER_HTTP_ATTEMPTS:-3}"

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
  echo "[status-sampler] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

sampler_secret="$(strip_wrapping_quotes "$(read_env_value STATUS_SAMPLER_SECRET || true)")"
base_url="$(strip_wrapping_quotes "$(read_env_value STATUS_SAMPLER_BASE_URL || true)")"
timeout_raw="$(strip_wrapping_quotes "$(read_env_value STATUS_SAMPLER_TIMEOUT_SECONDS || true)")"

if [[ -z "${sampler_secret}" ]]; then
  echo "[status-sampler] missing STATUS_SAMPLER_SECRET" >&2
  exit 1
fi

if [[ -z "${base_url}" ]]; then
  base_url="${BASE_URL_DEFAULT}"
fi

if [[ -z "${timeout_raw}" || ! "${timeout_raw}" =~ ^[0-9]+$ ]]; then
  timeout_raw="${TIMEOUT_DEFAULT}"
fi

if (( timeout_raw < 3 )); then
  timeout_raw=3
elif (( timeout_raw > 120 )); then
  timeout_raw=120
fi

if [[ -z "${WAIT_FOR_APP_SECONDS}" || ! "${WAIT_FOR_APP_SECONDS}" =~ ^[0-9]+$ ]]; then
  WAIT_FOR_APP_SECONDS="20"
fi
if (( WAIT_FOR_APP_SECONDS < 0 )); then
  WAIT_FOR_APP_SECONDS=0
elif (( WAIT_FOR_APP_SECONDS > 120 )); then
  WAIT_FOR_APP_SECONDS=120
fi

if [[ -z "${HTTP_ATTEMPTS}" || ! "${HTTP_ATTEMPTS}" =~ ^[0-9]+$ ]]; then
  HTTP_ATTEMPTS="3"
fi
if (( HTTP_ATTEMPTS < 1 )); then
  HTTP_ATTEMPTS=1
elif (( HTTP_ATTEMPTS > 6 )); then
  HTTP_ATTEMPTS=6
fi

sample_url="${base_url%/}/api/v1/internal/status-sample"
health_url="${base_url%/}/healthz"
body_file="$(mktemp /tmp/status-sampler.XXXXXX.json)"
trap 'rm -f "${body_file}"' EXIT

ready=0
if (( WAIT_FOR_APP_SECONDS == 0 )); then
  ready=1
else
  for _ in $(seq 1 "${WAIT_FOR_APP_SECONDS}"); do
    if curl -fsS --max-time 3 "${health_url}" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
fi
if (( ready != 1 )); then
  echo "[status-sampler] app not ready url=${health_url}" >&2
  exit 1
fi

http_code=""
for attempt in $(seq 1 "${HTTP_ATTEMPTS}"); do
  http_code="$(
    curl -sS \
      --max-time "${timeout_raw}" \
      -o "${body_file}" \
      -w "%{http_code}" \
      -X POST "${sample_url}" \
      -H "Content-Type: application/json" \
      -H "X-Status-Sampler-Secret: ${sampler_secret}" \
      -d "{}" || true
  )"
  if [[ "${http_code}" == "200" ]]; then
    break
  fi
  if (( attempt < HTTP_ATTEMPTS )); then
    sleep 1
  fi
done

if [[ "${http_code}" != "200" ]]; then
  echo "[status-sampler] failed http=${http_code} url=${sample_url}" >&2
  cat "${body_file}" >&2 || true
  exit 1
fi

python3 - "${body_file}" <<'PY'
from __future__ import annotations
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
print(
    "[status-sampler] ok"
    f" sampled_at={str(payload.get('sampled_at_utc', ''))}"
    f" services={int(payload.get('service_total', 0) or 0)}"
    f" online={int(summary.get('online', 0) or 0)}"
    f" degraded={int(summary.get('degraded', 0) or 0)}"
    f" offline={int(summary.get('offline', 0) or 0)}"
)
PY
