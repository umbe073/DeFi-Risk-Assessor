"""Request/device/IP security context helpers."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import time
from threading import Lock
from typing import Any, Dict, Optional
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest


EU_COUNTRY_CODES = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
}

IP_INTEL_CACHE_MAX_ENTRIES = 4096
_IP_INTEL_CACHE: Dict[str, Dict[str, Any]] = {}
_IP_INTEL_CACHE_LOCK = Lock()


def country_flag(country_code: str) -> str:
    code = str(country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    base = 127397
    return chr(base + ord(code[0])) + chr(base + ord(code[1]))


def normalize_region(value: str) -> str:
    raw = str(value or "").strip().upper()
    if raw in {"EU", "US"}:
        return raw
    return "OTHER"


def region_from_country_code(country_code: str) -> str:
    code = str(country_code or "").strip().upper()
    if code == "US":
        return "US"
    if code in EU_COUNTRY_CODES:
        return "EU"
    return "OTHER"


def _parse_version(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""
    return str(match.group(1) or "").replace("_", ".")


def parse_user_agent(user_agent: str) -> Dict[str, str]:
    ua = str(user_agent or "").strip()
    low = ua.lower()
    if not ua:
        return {
            "device_type": "unknown",
            "os_name": "unknown",
            "os_version": "",
            "browser_name": "unknown",
            "browser_version": "",
        }

    device_type = "desktop"
    if "ipad" in low or "tablet" in low:
        device_type = "tablet"
    elif any(token in low for token in ["mobile", "iphone", "android"]):
        device_type = "mobile"
    elif any(token in low for token in ["bot", "spider", "crawler"]):
        device_type = "bot"

    os_name = "unknown"
    os_version = ""
    if "windows nt" in low:
        os_name = "windows"
        os_version = _parse_version(r"Windows NT ([0-9.]+)", ua)
    elif "android" in low:
        os_name = "android"
        os_version = _parse_version(r"Android ([0-9.]+)", ua)
    elif "iphone" in low or "ipad" in low:
        os_name = "ios"
        os_version = _parse_version(r"OS ([0-9_]+)", ua)
    elif "mac os x" in low:
        os_name = "macos"
        os_version = _parse_version(r"Mac OS X ([0-9_]+)", ua)
    elif "linux" in low:
        os_name = "linux"

    browser_name = "unknown"
    browser_version = ""
    if "edg/" in low:
        browser_name = "edge"
        browser_version = _parse_version(r"Edg/([0-9.]+)", ua)
    elif "opr/" in low:
        browser_name = "opera"
        browser_version = _parse_version(r"OPR/([0-9.]+)", ua)
    elif "chrome/" in low and "chromium" not in low:
        browser_name = "chrome"
        browser_version = _parse_version(r"Chrome/([0-9.]+)", ua)
    elif "firefox/" in low:
        browser_name = "firefox"
        browser_version = _parse_version(r"Firefox/([0-9.]+)", ua)
    elif "safari/" in low and "chrome/" not in low:
        browser_name = "safari"
        browser_version = _parse_version(r"Version/([0-9.]+)", ua)

    return {
        "device_type": device_type,
        "os_name": os_name,
        "os_version": os_version,
        "browser_name": browser_name,
        "browser_version": browser_version,
    }


def _to_nullable_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def _normalize_ip(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return text[:64]


def _is_safe_lookup_url_target(lookup_url: str) -> bool:
    try:
        parsed = urlparse.urlsplit(str(lookup_url or "").strip())
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False

    host = str(parsed.hostname).strip()
    try:
        host_ip = ipaddress.ip_address(host)
        if (
            host_ip.is_private
            or host_ip.is_loopback
            or host_ip.is_link_local
            or host_ip.is_multicast
            or host_ip.is_reserved
        ):
            return False
    except ValueError:
        pass

    return True


def _ip_intel_cache_key(*, ip_address: str, lookup_url: str, api_key: str) -> str:
    token = f"{ip_address}|{lookup_url}|{api_key}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ip_intel_cache_get(cache_key: str) -> Optional[Dict[str, Any]]:
    now_epoch = int(time.time())
    with _IP_INTEL_CACHE_LOCK:
        row = _IP_INTEL_CACHE.get(cache_key)
        if not row:
            return None
        expires_at = int(row.get("expires_at", 0) or 0)
        if expires_at <= now_epoch:
            _IP_INTEL_CACHE.pop(cache_key, None)
            return None
        payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    return dict(payload)


def _ip_intel_cache_put(*, cache_key: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
    now_epoch = int(time.time())
    ttl = max(30, int(ttl_seconds))
    with _IP_INTEL_CACHE_LOCK:
        _IP_INTEL_CACHE[cache_key] = {
            "expires_at": now_epoch + ttl,
            "payload": dict(payload),
        }
        if len(_IP_INTEL_CACHE) <= IP_INTEL_CACHE_MAX_ENTRIES:
            return

        stale_keys = [key for key, row in _IP_INTEL_CACHE.items() if int(row.get("expires_at", 0) or 0) <= now_epoch]
        for stale_key in stale_keys:
            _IP_INTEL_CACHE.pop(stale_key, None)
        if len(_IP_INTEL_CACHE) <= IP_INTEL_CACHE_MAX_ENTRIES:
            return

        oldest = sorted(
            _IP_INTEL_CACHE.items(),
            key=lambda item: int(item[1].get("expires_at", 0) or 0),
        )
        trim_count = len(_IP_INTEL_CACHE) - IP_INTEL_CACHE_MAX_ENTRIES
        for key, _ in oldest[:trim_count]:
            _IP_INTEL_CACHE.pop(key, None)


def default_ip_intel(ip_address: str) -> Dict[str, Any]:
    ip = _normalize_ip(ip_address)
    country_code = ""
    country_name = ""
    try:
        parsed = ipaddress.ip_address(ip)
        if parsed.is_private or parsed.is_loopback:
            country_name = "Private network"
    except ValueError:
        pass
    return {
        "ip_address": ip,
        "country_code": country_code,
        "country_name": country_name,
        "country_flag": country_flag(country_code),
        "is_vpn": None,
        "is_residential_proxy": None,
        "is_other_proxy": None,
        "is_datacenter": None,
        "is_hosting": None,
        "intel_source": "none",
    }


def lookup_ip_intel(
    *,
    ip_address: str,
    lookup_url: str = "",
    api_key: str = "",
    timeout_seconds: int = 4,
    cache_ttl_seconds: int = 300,
) -> Dict[str, Any]:
    base = default_ip_intel(ip_address)
    lookup_url = str(lookup_url or "").strip()
    if not lookup_url:
        return base
    if not _is_safe_lookup_url_target(lookup_url):
        base["intel_source"] = "lookup_failed"
        return base

    ip = str(base.get("ip_address", "")).strip()
    if not ip:
        return base

    url_template = lookup_url
    if "{api_key}" in url_template:
        url_template = url_template.replace("{api_key}", urlparse.quote(api_key, safe=""))

    if "{ip}" in url_template:
        url = url_template.replace("{ip}", urlparse.quote(ip, safe=""))
    else:
        sep = "&" if "?" in url_template else "?"
        url = f"{url_template}{sep}ip={urlparse.quote(ip, safe='')}"

    cache_key = _ip_intel_cache_key(ip_address=ip, lookup_url=url_template, api_key=api_key)
    cached = _ip_intel_cache_get(cache_key)
    if isinstance(cached, dict):
        return cached

    req = urlrequest.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    if api_key and "{api_key}" not in lookup_url:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urlrequest.urlopen(req, timeout=max(2, int(timeout_seconds))) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urlerror.URLError, TimeoutError, ValueError, OSError):
        base["intel_source"] = "lookup_failed"
        _ip_intel_cache_put(cache_key=cache_key, payload=base, ttl_seconds=cache_ttl_seconds)
        return base

    if not isinstance(payload, dict):
        base["intel_source"] = "invalid_payload"
        _ip_intel_cache_put(cache_key=cache_key, payload=base, ttl_seconds=cache_ttl_seconds)
        return base

    proxy_payload = payload.get("proxy")
    if not isinstance(proxy_payload, dict):
        proxy_payload = {}
    security_payload = payload.get("security")
    if not isinstance(security_payload, dict):
        security_payload = {}
    as_info_payload = payload.get("as_info")
    if not isinstance(as_info_payload, dict):
        as_info_payload = {}
    country_payload = payload.get("country")
    if not isinstance(country_payload, dict):
        country_payload = {}

    country_code = str(
        payload.get("country_code")
        or payload.get("countryCode")
        or payload.get("country_iso")
        or payload.get("country_code2")
        or country_payload.get("code")
        or payload.get("isocode")
        or ""
    ).strip().upper()
    if len(country_code) != 2:
        country_code = ""
    country_name = str(
        payload.get("country_name")
        or payload.get("countryName")
        or payload.get("country_full")
        or country_payload.get("name")
        or payload.get("country")
        or ""
    ).strip()

    is_proxy = _to_nullable_bool(payload.get("is_proxy", proxy_payload.get("is_proxy")))
    proxy_type = str(payload.get("proxy_type") or proxy_payload.get("proxy_type") or "").strip().upper()
    usage_type = str(payload.get("usage_type") or as_info_payload.get("as_usage_type") or "").strip().upper()

    is_vpn = _to_nullable_bool(
        payload.get(
            "is_vpn",
            payload.get(
                "vpn",
                payload.get(
                    "isVPN",
                    payload.get(
                        "is_anonymous_vpn",
                        security_payload.get("is_vpn", security_payload.get("is_anonymous_vpn", proxy_payload.get("is_vpn"))),
                    ),
                ),
            ),
        )
    )
    if is_vpn is None and proxy_type == "VPN":
        is_vpn = True

    is_residential_proxy = _to_nullable_bool(
        payload.get(
            "is_residential_proxy",
            payload.get(
                "residential_proxy",
                payload.get(
                    "is_res",
                    payload.get(
                        "isResidentialProxy",
                        security_payload.get("is_residential_proxy", proxy_payload.get("is_residential_proxy")),
                    ),
                ),
            ),
        )
    )
    if is_residential_proxy is None and proxy_type == "RES":
        is_residential_proxy = True

    is_datacenter = _to_nullable_bool(
        payload.get(
            "is_datacenter",
            payload.get(
                "datacenter",
                payload.get("is_dc", payload.get("isDataCenter", proxy_payload.get("is_data_center"))),
            ),
        )
    )
    if is_datacenter is None:
        is_datacenter = _to_nullable_bool(
            security_payload.get(
                "is_datacenter",
                security_payload.get("is_data_center", security_payload.get("is_server")),
            )
        )
    if is_datacenter is None and (proxy_type == "DCH" or usage_type in {"DCH", "CDN"}):
        is_datacenter = True

    is_hosting = _to_nullable_bool(
        payload.get(
            "is_hosting",
            payload.get(
                "hosting",
                payload.get(
                    "isHosting",
                    payload.get(
                        "is_server",
                        security_payload.get("is_hosting", security_payload.get("is_server", proxy_payload.get("is_data_center"))),
                    ),
                ),
            ),
        )
    )
    if is_hosting is None and is_datacenter is True:
        is_hosting = True

    is_other_proxy = _to_nullable_bool(
        payload.get(
            "is_other_proxy",
            payload.get(
                "is_proxy",
                payload.get("proxy", payload.get("isProxy", proxy_payload.get("is_public_proxy"))),
            ),
        )
    )
    if is_other_proxy is None:
        is_other_proxy = _to_nullable_bool(
            security_payload.get(
                "is_other_proxy",
                security_payload.get("is_public_proxy", security_payload.get("is_proxy")),
            )
        )
    if is_other_proxy is None and proxy_type in {"PUB", "WEB", "TOR", "CPN", "EPN"}:
        is_other_proxy = True
    if is_other_proxy is None and is_proxy is True and not (is_vpn is True or is_residential_proxy is True):
        is_other_proxy = True

    result = {
        "ip_address": ip,
        "country_code": country_code,
        "country_name": country_name,
        "country_flag": country_flag(country_code),
        "is_vpn": is_vpn,
        "is_residential_proxy": is_residential_proxy,
        "is_other_proxy": is_other_proxy,
        "is_datacenter": is_datacenter,
        "is_hosting": is_hosting,
        "intel_source": "lookup",
    }
    _ip_intel_cache_put(cache_key=cache_key, payload=result, ttl_seconds=cache_ttl_seconds)
    return result
