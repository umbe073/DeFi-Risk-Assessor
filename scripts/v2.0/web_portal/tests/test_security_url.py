from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import security_url as su  # noqa: E402


def test_sanitize_header_value_strips_crlf() -> None:
    assert su.sanitize_header_value("a\nb\r\nc") == "abc"


def test_safe_relative_path_rejects_protocol_relative() -> None:
    assert su.safe_relative_path("/dashboard") == "/dashboard"
    assert su.safe_relative_path("//evil.com") is None
    assert su.safe_relative_path("https://x") is None


def test_is_https_url_host_allowed() -> None:
    assert su.is_https_url_host_allowed("https://app.hodler-suite.com/x", ("hodler-suite.com",)) is True
    assert su.is_https_url_host_allowed("https://evil.com/x", ("hodler-suite.com",)) is False
    assert su.is_https_url_host_allowed("http://app.hodler-suite.com/x", ("hodler-suite.com",)) is False


def test_redact_url_query_for_log() -> None:
    u = "https://api.example.com/v1?api_key=SECRET&x=1"
    out = su.redact_url_query_for_log(u)
    assert "SECRET" not in out
    assert "redacted" in out.lower() or "[redacted]" in out


def test_join_trusted_base_url_blocks_protocol_relative_suffix() -> None:
    joined = su.join_trusted_base_url("https://app.example.com", "//evil.com/path")
    assert joined.endswith("/")
