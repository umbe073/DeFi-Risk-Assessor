"""Minimal TOTP helpers (RFC 6238 compatible)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from urllib.parse import quote


def generate_totp_secret() -> str:
    """Create a base32 secret suitable for authenticator apps."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("utf-8").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    # Accept common human-formatted secrets (spaces, dashes, separators) by
    # stripping non-base32 characters before decoding.
    compact = re.sub(r"[^A-Z2-7]", "", "".join(str(secret or "").strip().split()).upper())
    if not compact:
        raise ValueError("Missing TOTP secret")
    pad = (-len(compact)) % 8
    compact = compact + ("=" * pad)
    return base64.b32decode(compact, casefold=True)


def _totp_code(secret: str, timestamp: int, interval: int = 30, digits: int = 6) -> str:
    key = _normalize_secret(secret)
    counter = int(timestamp // interval)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = binary % (10**digits)
    return str(code).zfill(digits)


def verify_totp_code(secret: str, code: str, *, window: int = 1, interval: int = 30, digits: int = 6) -> bool:
    cleaned = "".join(ch for ch in str(code or "").strip() if ch.isdigit())
    if not cleaned.isdigit() or len(cleaned) != digits:
        return False

    try:
        now = int(time.time())
        for offset in range(-window, window + 1):
            if _totp_code(secret, now + (offset * interval), interval=interval, digits=digits) == cleaned:
                return True
        return False
    except Exception:
        return False


def build_otpauth_uri(secret: str, email: str, issuer: str) -> str:
    label = quote(f"{issuer}:{email}")
    issuer_q = quote(issuer)
    secret_q = quote(secret)
    return f"otpauth://totp/{label}?secret={secret_q}&issuer={issuer_q}&algorithm=SHA1&digits=6&period=30"
