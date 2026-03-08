"""Cloudflare Turnstile verification helper."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple
from urllib import parse as urlparse
from urllib import request as urlrequest


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(*, secret_key: str, response_token: str, remote_ip: str = "") -> Tuple[bool, str]:
    secret = str(secret_key or "").strip()
    token = str(response_token or "").strip()
    if not secret:
        return False, "turnstile_not_configured"
    if not token:
        return False, "missing_turnstile_token"

    payload = {
        "secret": secret,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = str(remote_ip).strip()

    encoded = urlparse.urlencode(payload).encode("utf-8")
    req = urlrequest.Request(
        TURNSTILE_VERIFY_URL,
        method="POST",
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urlrequest.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8", "replace")
    except Exception as exc:  # pragma: no cover - network dependency
        return False, f"turnstile_network_error:{exc}"

    try:
        decoded: Dict[str, Any] = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return False, "turnstile_invalid_response"

    if bool(decoded.get("success")):
        return True, ""

    errors = decoded.get("error-codes")
    if isinstance(errors, list) and errors:
        return False, f"turnstile_failed:{','.join(str(item) for item in errors)}"
    return False, "turnstile_failed"
