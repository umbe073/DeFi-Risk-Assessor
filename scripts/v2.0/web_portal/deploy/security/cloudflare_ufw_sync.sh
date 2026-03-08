#!/usr/bin/env bash
set -Eeuo pipefail

# Sync Cloudflare IP ranges into UFW allow rules for HTTPS/HTTP origin access.
# Intended to run from systemd timer (monthly) with zero manual interaction.

CF_V4_URL="${CF_V4_URL:-https://www.cloudflare.com/ips-v4}"
CF_V6_URL="${CF_V6_URL:-https://www.cloudflare.com/ips-v6}"
UFW_PORTS="${UFW_PORTS:-80,443}"
COMMENT_V4="${COMMENT_V4:-cf-auto-v4}"
COMMENT_V6="${COMMENT_V6:-cf-auto-v6}"
TMPDIR="${TMPDIR:-/tmp}"
DRY_RUN="${DRY_RUN:-0}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: run as root" >&2
  exit 1
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: missing required command: $1" >&2
    exit 1
  }
}

need_cmd curl
need_cmd ufw
need_cmd awk
need_cmd sed
need_cmd sort

v4_file="$(mktemp "${TMPDIR%/}/cf-v4.XXXXXX")"
v6_file="$(mktemp "${TMPDIR%/}/cf-v6.XXXXXX")"
trap 'rm -f "${v4_file}" "${v6_file}"' EXIT

echo "[cf-ufw-sync] downloading Cloudflare ranges"
curl -fsSL "${CF_V4_URL}" -o "${v4_file}"
curl -fsSL "${CF_V6_URL}" -o "${v6_file}"

mapfile -t v4_cidrs < <(awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\/[0-9]+$/{print $0}' "${v4_file}")
mapfile -t v6_cidrs < <(awk '/^[0-9a-fA-F:]+\/[0-9]+$/{print $0}' "${v6_file}")

if [[ "${#v4_cidrs[@]}" -eq 0 && "${#v6_cidrs[@]}" -eq 0 ]]; then
  echo "error: no valid Cloudflare CIDRs parsed, keeping current rules unchanged" >&2
  exit 1
fi

delete_tagged_rules() {
  local tag="$1"
  mapfile -t numbers < <(
    ufw status numbered \
      | awk -v t="# ${tag}" 'index($0,t)>0 {gsub(/\[/,"",$1); gsub(/\]/,"",$1); print $1}' \
      | sort -rn
  )
  for n in "${numbers[@]}"; do
    if [[ "${DRY_RUN}" == "1" ]]; then
      echo "[dry-run] ufw --force delete ${n}"
    else
      ufw --force delete "${n}" >/dev/null
    fi
  done
}

add_rules() {
  local tag="$1"
  shift
  local cidr
  for cidr in "$@"; do
    if [[ "${DRY_RUN}" == "1" ]]; then
      echo "[dry-run] ufw allow proto tcp from ${cidr} to any port ${UFW_PORTS} comment ${tag}"
    else
      ufw allow proto tcp from "${cidr}" to any port "${UFW_PORTS}" comment "${tag}" >/dev/null
    fi
  done
}

echo "[cf-ufw-sync] removing old tagged rules"
delete_tagged_rules "${COMMENT_V4}"
delete_tagged_rules "${COMMENT_V6}"

echo "[cf-ufw-sync] adding new rules: ipv4=${#v4_cidrs[@]} ipv6=${#v6_cidrs[@]}"
add_rules "${COMMENT_V4}" "${v4_cidrs[@]}"
add_rules "${COMMENT_V6}" "${v6_cidrs[@]}"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[dry-run] ufw --force reload"
else
  ufw --force reload >/dev/null
fi

echo "[cf-ufw-sync] done"
