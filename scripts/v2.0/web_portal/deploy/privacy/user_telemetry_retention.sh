#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${USER_TELEMETRY_ENV_FILE:-/opt/hodler-suite/web_portal/web_portal.env}"
APP_ROOT="${USER_TELEMETRY_APP_ROOT:-/opt/hodler-suite/web_portal}"
DEFAULT_AUTH_DB="/opt/hodler-suite/web_portal/data/web_portal_auth.db"

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
  echo "[user-telemetry-retention] missing env file: ${ENV_FILE}" >&2
  exit 1
fi

enabled_raw="$(strip_wrapping_quotes "$(read_env_value USER_TELEMETRY_RETENTION_ENABLED || true)")"
if [[ -z "${enabled_raw}" ]]; then
  enabled_raw="true"
fi
if ! to_bool "${enabled_raw}"; then
  echo "[user-telemetry-retention] skipped (USER_TELEMETRY_RETENTION_ENABLED is false)"
  exit 0
fi

auth_db="$(strip_wrapping_quotes "$(read_env_value WEB_PORTAL_AUTH_DB || true)")"
operation_days="$(strip_wrapping_quotes "$(read_env_value USER_OPERATION_RETENTION_DAYS || true)")"
device_days="$(strip_wrapping_quotes "$(read_env_value USER_DEVICE_RETENTION_DAYS || true)")"
login_days="$(strip_wrapping_quotes "$(read_env_value USER_LOGIN_CONTEXT_RETENTION_DAYS || true)")"
dry_run_raw="$(strip_wrapping_quotes "$(read_env_value USER_TELEMETRY_PURGE_DRY_RUN || true)")"

if [[ -z "${auth_db}" ]]; then
  auth_db="${DEFAULT_AUTH_DB}"
fi
if [[ -z "${operation_days}" || ! "${operation_days}" =~ ^[0-9]+$ ]]; then
  operation_days="180"
fi
if [[ -z "${device_days}" || ! "${device_days}" =~ ^[0-9]+$ ]]; then
  device_days="180"
fi
if [[ -z "${login_days}" || ! "${login_days}" =~ ^[0-9]+$ ]]; then
  login_days="90"
fi

if (( operation_days < 1 )); then
  operation_days=1
fi
if (( device_days < 1 )); then
  device_days=1
fi
if (( login_days < 1 )); then
  login_days=1
fi

purge_script="${APP_ROOT%/}/deploy/privacy/purge_user_telemetry.py"
if [[ ! -f "${purge_script}" ]]; then
  echo "[user-telemetry-retention] missing purge script: ${purge_script}" >&2
  exit 1
fi

python_bin="${APP_ROOT%/}/.venv/bin/python3"
if [[ ! -x "${python_bin}" ]]; then
  python_bin="python3"
fi

args=(
  --db "${auth_db}"
  --operation-days "${operation_days}"
  --device-days "${device_days}"
  --login-context-days "${login_days}"
)
if to_bool "${dry_run_raw}"; then
  args+=(--dry-run)
fi

PYTHONPATH="${APP_ROOT%/}:${PYTHONPATH:-}" "${python_bin}" "${purge_script}" "${args[@]}"
