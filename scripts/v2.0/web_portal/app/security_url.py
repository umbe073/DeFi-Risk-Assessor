"""URL, host, and header validation for redirects and outbound safety checks."""

from __future__ import annotations

import os
import re
from typing import Collection, Optional, Set
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

_HEADER_NEWLINES = re.compile(r"[\r\n]+")


def sanitize_header_value(value: str, *, max_length: int = 1024) -> str:
    """Remove CR/LF to mitigate HTTP response splitting; trim length."""
    text = str(value or "")
    text = _HEADER_NEWLINES.sub("", text)
    if len(text) > max_length:
        text = text[:max_length]
    return text.strip()


def parse_hostname(url: str) -> str:
    try:
        return str(urlparse(str(url or "").strip()).hostname or "").lower().strip().strip(".")
    except ValueError:
        return ""


def hostname_under(hostname: Optional[str], root: str) -> bool:
    """True if hostname is root or a proper subdomain of root (no substring tricks)."""
    host = (hostname or "").strip().lower().strip(".")
    root_norm = (root or "").strip().lower().strip(".")
    if not host or not root_norm:
        return False
    return host == root_norm or host.endswith("." + root_norm)


def is_https_url_host_allowed(url: str, allowed_hosts: Collection[str]) -> bool:
    try:
        parsed = urlparse(str(url or "").strip())
    except ValueError:
        return False
    if parsed.scheme.lower() != "https":
        return False
    if parsed.username or parsed.password:
        return False
    host = parse_hostname(str(url or ""))
    if not host:
        return False
    for allowed in allowed_hosts:
        a = str(allowed or "").strip().lower().strip(".")
        if not a:
            continue
        if hostname_under(host, a) or host == a:
            return True
    return False


def safe_relative_path(candidate: str) -> Optional[str]:
    """Allow only same-site path redirects; block scheme-relative and header injection."""
    raw = str(candidate or "").strip()
    if not raw.startswith("/") or raw.startswith("//"):
        return None
    if any(ch in raw for ch in ("\r", "\n", "\x00")):
        return None
    return raw


def merge_allowed_hosts_from_settings(settings: object) -> Set[str]:
    """Hostnames derived from configured portal base URLs (for open-redirect checks)."""
    hosts: Set[str] = set()
    for attr in (
        "web_portal_app_base_url",
        "web_portal_public_base_url",
        "web_portal_marketing_base_url",
    ):
        raw = str(getattr(settings, attr, "") or "").strip()
        if not raw:
            continue
        host = parse_hostname(raw)
        if host:
            hosts.add(host)
    extra = str(os.environ.get("PORTAL_REDIRECT_EXTRA_HOSTS", "") or "").strip()
    for piece in extra.split(","):
        h = piece.strip().lower().strip(".")
        if h:
            hosts.add(h)
    return hosts


def safe_next_location(
    candidate: Optional[str],
    *,
    allowed_hosts: Collection[str],
    fallback_path: str,
) -> str:
    """
    Return a safe local path or an https URL whose host is in allowed_hosts.
    `fallback_path` is typically a url_for() string (path only).
    """
    fb = safe_relative_path(fallback_path) or "/"
    if not candidate:
        return fb
    raw = str(candidate).strip()
    rel = safe_relative_path(raw)
    if rel is not None:
        return rel
    if is_https_url_host_allowed(raw, allowed_hosts):
        return raw
    return fb


def join_trusted_base_url(base_url: str, path_and_query: str) -> str:
    """Join configured site base with a safe same-site path/query suffix."""
    base = str(base_url or "").strip().rstrip("/")
    raw_suffix = str(path_and_query or "").strip()

    # Normalize browser-tolerated separators and block header/control chars.
    normalized = raw_suffix.replace("\\", "/")
    if any(ch in normalized for ch in ("\r", "\n", "\x00")):
        normalized = "/"

    # Disallow absolute/scheme-relative forms; require local absolute path.
    parsed = urlparse(normalized)
    if parsed.scheme or parsed.netloc:
        normalized = "/"
        parsed = urlparse(normalized)

    path = str(parsed.path or "")
    if not path.startswith("/") or path.startswith("//"):
        path = "/"

    suffix = urlunparse(("", "", path, "", parsed.query, parsed.fragment))
    return f"{base}{suffix}"


def require_https_hostname(url: str, allowed_hostnames: Collection[str]) -> None:
    """Raise ValueError if url is not https or host is not in the allowlist."""
    if not is_https_url_host_allowed(url, allowed_hostnames):
        raise ValueError("url_host_not_allowed")


_ALLOWED_RESEND_HOSTS = frozenset({"api.resend.com"})
_ALLOWED_GITHUB_API_HOSTS = frozenset({"api.github.com"})


def assert_slack_incoming_webhook_url(url: str) -> None:
    try:
        parsed = urlparse(str(url or "").strip())
    except ValueError as exc:
        raise ValueError("invalid_slack_webhook_url") from exc
    if parsed.scheme.lower() != "https":
        raise ValueError("slack_webhook_must_be_https")
    host = parse_hostname(str(url or ""))
    if host != "hooks.slack.com":
        raise ValueError("slack_webhook_host_not_allowed")


def assert_resend_https_url(url: str) -> None:
    require_https_hostname(url, _ALLOWED_RESEND_HOSTS)


def assert_github_api_url(url: str) -> None:
    require_https_hostname(url, _ALLOWED_GITHUB_API_HOSTS)


def redact_url_query_for_log(url: str, sensitive_keys: Optional[Collection[str]] = None) -> str:
    """Strip sensitive query parameters from URLs before logging."""
    keys = {k.lower() for k in (sensitive_keys or ())} | {
        "apikey",
        "api_key",
        "key",
        "token",
        "secret",
        "password",
        "auth",
    }
    try:
        parsed = urlparse(str(url or ""))
        if not parsed.query:
            return str(url or "")
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        redacted: list[tuple[str, str]] = []
        for k, v in pairs:
            if k.lower() in keys:
                redacted.append((k, "[redacted]"))
            else:
                redacted.append((k, v))
        new_query = urlencode(redacted, quote_via=quote)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return "[unparseable_url]"


def redact_headers_for_log(headers: object) -> dict[str, str]:
    """Return a copy of headers safe to print (API keys redacted)."""
    if not isinstance(headers, dict):
        return {}
    sensitive = {
        "authorization",
        "cookie",
        "x-api-key",
        "x-cg-pro-api-key",
        "x-cg-demo-api-key",
        "x-webhook-signature",
        "x-webhook-timestamp",
    }
    out: dict[str, str] = {}
    for key, value in headers.items():
        lk = str(key or "").lower()
        if lk in sensitive:
            out[str(key)] = "[redacted]"
        else:
            out[str(key)] = str(value)
    return out
