from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import security_context as sc  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_ip_intel_cache() -> None:
    sc._IP_INTEL_CACHE.clear()
    yield
    sc._IP_INTEL_CACHE.clear()


@contextmanager
def _mock_lookup_payload(payload: object):
    raw = json.dumps(payload).encode("utf-8")

    class _Resp:
        def read(self) -> bytes:
            return raw

    yield _Resp()


def test_lookup_ip_intel_allows_public_dns_target(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"ip": "8.8.8.8", "country_code": "US", "country_name": "United States"}

    def _fake_getaddrinfo(host: str, port: int, *args: object, **kwargs: object) -> list[tuple[object, ...]]:
        assert host == "api.example.com"
        return [(sc.socket.AF_INET, sc.socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]

    monkeypatch.setattr(sc.socket, "getaddrinfo", _fake_getaddrinfo)
    with patch.object(sc, "_open_lookup_request", return_value=_mock_lookup_payload(body)):
        row = sc.lookup_ip_intel(
            ip_address="8.8.8.8",
            lookup_url="https://api.example.com/intel?ip={ip}",
            cache_ttl_seconds=30,
        )

    assert row["intel_source"] == "lookup"
    assert row["country_code"] == "US"


def test_lookup_ip_intel_blocks_localhost_before_request() -> None:
    with (
        patch.object(sc.socket, "getaddrinfo") as resolve_mock,
        patch.object(sc, "_open_lookup_request") as open_mock,
    ):
        row = sc.lookup_ip_intel(
            ip_address="8.8.8.8",
            lookup_url="http://localhost/intel?ip={ip}",
            cache_ttl_seconds=30,
        )

    assert row["intel_source"] == "lookup_failed"
    resolve_mock.assert_not_called()
    open_mock.assert_not_called()


def test_lookup_ip_intel_blocks_metadata_internal_before_request() -> None:
    with (
        patch.object(sc.socket, "getaddrinfo") as resolve_mock,
        patch.object(sc, "_open_lookup_request") as open_mock,
    ):
        row = sc.lookup_ip_intel(
            ip_address="8.8.8.8",
            lookup_url="http://metadata.google.internal/computeMetadata/v1/?ip={ip}",
            cache_ttl_seconds=30,
        )

    assert row["intel_source"] == "lookup_failed"
    resolve_mock.assert_not_called()
    open_mock.assert_not_called()


def test_lookup_ip_intel_blocks_dns_name_resolving_to_loopback() -> None:
    with (
        patch.object(
            sc.socket,
            "getaddrinfo",
            return_value=[(sc.socket.AF_INET, sc.socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
        ),
        patch.object(sc, "_open_lookup_request") as open_mock,
    ):
        row = sc.lookup_ip_intel(
            ip_address="8.8.8.8",
            lookup_url="http://127.0.0.1.nip.io/intel?ip={ip}",
            cache_ttl_seconds=30,
        )

    assert row["intel_source"] == "lookup_failed"
    open_mock.assert_not_called()


def test_lookup_url_target_rejects_private_ip_literals() -> None:
    assert sc._is_safe_lookup_url_target("http://127.0.0.1/intel") is False
    assert sc._is_safe_lookup_url_target("http://[::1]/intel") is False
    assert sc._is_safe_lookup_url_target("http://169.254.169.254/latest/meta-data") is False
