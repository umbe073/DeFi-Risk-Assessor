#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${RISK_WORKER_ENV_FILE:-/opt/hodler-suite/web_portal/web_portal.env}"
BASE_URL_DEFAULT="http://127.0.0.1:5050"
TIMEOUT_DEFAULT="40"
WAIT_FOR_APP_SECONDS="${RISK_WORKER_WAIT_FOR_APP_SECONDS:-20}"

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
  echo "[risk-worker] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

risk_secret="$(strip_wrapping_quotes "$(read_env_value RISK_WORKER_SHARED_SECRET || true)")"
if [[ -z "${risk_secret}" ]]; then
  risk_secret="$(strip_wrapping_quotes "$(read_env_value WEBHOOK_SHARED_SECRET || true)")"
fi

base_url="$(strip_wrapping_quotes "$(read_env_value RISK_WORKER_BASE_URL || true)")"
timeout_raw="$(strip_wrapping_quotes "$(read_env_value RISK_WORKER_TIMEOUT_SECONDS || true)")"
worker_id_raw="$(strip_wrapping_quotes "$(read_env_value RISK_WORKER_ID || true)")"

if [[ -z "${risk_secret}" ]]; then
  echo "[risk-worker] missing RISK_WORKER_SHARED_SECRET (and WEBHOOK_SHARED_SECRET fallback empty)" >&2
  exit 1
fi

if [[ -z "${base_url}" ]]; then
  base_url="${BASE_URL_DEFAULT}"
fi

if [[ -z "${timeout_raw}" || ! "${timeout_raw}" =~ ^[0-9]+$ ]]; then
  timeout_raw="${TIMEOUT_DEFAULT}"
fi
if (( timeout_raw < 5 )); then
  timeout_raw=5
elif (( timeout_raw > 180 )); then
  timeout_raw=180
fi

if [[ -z "${WAIT_FOR_APP_SECONDS}" || ! "${WAIT_FOR_APP_SECONDS}" =~ ^[0-9]+$ ]]; then
  WAIT_FOR_APP_SECONDS=20
fi
if (( WAIT_FOR_APP_SECONDS < 0 )); then
  WAIT_FOR_APP_SECONDS=0
elif (( WAIT_FOR_APP_SECONDS > 120 )); then
  WAIT_FOR_APP_SECONDS=120
fi

if [[ -z "${worker_id_raw}" ]]; then
  worker_id_raw="risk-worker-${HOSTNAME:-node}"
fi
worker_id="$(printf "%s" "${worker_id_raw}" | tr -cd '[:alnum:]_.:-')"
if [[ -z "${worker_id}" ]]; then
  worker_id="risk-worker"
fi

health_url="${base_url%/}/healthz"
run_url="${base_url%/}/api/v1/risk/internal/run-once"
body_file="$(mktemp /tmp/risk-worker.XXXXXX.json)"
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
  echo "[risk-worker] app not ready url=${health_url}" >&2
  exit 1
fi

payload="{\"worker_id\":\"${worker_id}\"}"
http_code="$(
  curl -sS \
    --max-time "${timeout_raw}" \
    -o "${body_file}" \
    -w "%{http_code}" \
    -X POST "${run_url}" \
    -H "Content-Type: application/json" \
    -H "X-Risk-Worker-Secret: ${risk_secret}" \
    -d "${payload}"
)"

if [[ "${http_code}" != "200" ]]; then
  echo "[risk-worker] failed http=${http_code} url=${run_url}" >&2
  cat "${body_file}" >&2 || true
  exit 1
fi

python3 - "${body_file}" <<'PY'
from __future__ import annotations
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
status = str(payload.get("status", ""))
processed = bool(payload.get("processed", False))
claimed = bool(payload.get("claimed", processed))
job = payload.get("job", {}) if isinstance(payload.get("job"), dict) else {}
result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}

job_id = str(job.get("job_id", ""))
job_status = str(job.get("status", ""))
risk_score = result.get("risk_score")

parts = [
    "[risk-worker]",
    f"status={status or 'unknown'}",
    f"processed={processed}",
    f"claimed={claimed}",
]
if job_id:
    parts.append(f"job_id={job_id}")
if job_status:
    parts.append(f"job_status={job_status}")
if risk_score is not None:
    parts.append(f"risk_score={risk_score}")
print(" ".join(parts))

if status == "failed":
    sys.exit(1)
PY

