#!/usr/bin/env python3
"""Minimal webhook server with defensive request validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

MAX_BODY_BYTES = 1024 * 1024  # 1 MiB


def parse_signature(signature_header: str) -> tuple[str | None, str | None]:
    """Return (algorithm, hex digest) from an X-Hub-Signature-256 style header."""
    if not signature_header or "=" not in signature_header:
        return None, None
    algorithm, digest = signature_header.split("=", 1)
    if not algorithm or not digest:
        return None, None
    return algorithm.strip().lower(), digest.strip().lower()


def verify_signature(secret: str, body: bytes, signature_header: str) -> bool:
    """Verify HMAC signature in constant time."""
    algorithm, digest = parse_signature(signature_header)
    if algorithm != "sha256" or not digest:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def validate_payload(payload: Any) -> tuple[bool, str]:
    """Validate webhook payload shape to avoid runtime key errors."""
    if not isinstance(payload, dict):
        return False, "payload must be a JSON object"
    if not isinstance(payload.get("event"), str) or not payload["event"].strip():
        return False, "missing required field: event"
    if "data" not in payload:
        return False, "missing required field: data"
    if not isinstance(payload["data"], dict):
        return False, "field data must be an object"
    return True, ""


def process_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize webhook metadata for downstream processing."""
    return {
        "accepted": True,
        "event": payload["event"],
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler that receives POST /webhook events."""

    server_version = "WebhookServer/1.0"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
        parsed_path = urlparse(self.path)
        if parsed_path.path != "/webhook":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid Content-Length"})
            return

        if content_length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "request body is empty"})
            return
        if content_length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "payload too large"})
            return

        body = self.rfile.read(content_length)
        if len(body) != content_length:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "incomplete request body"})
            return

        secret = os.getenv("WEBHOOK_SECRET", "")
        if secret:
            provided = self.headers.get("X-Hub-Signature-256", "")
            if not verify_signature(secret, body, provided):
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "invalid signature"})
                return

        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON payload"})
            return

        valid, reason = validate_payload(payload)
        if not valid:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": reason})
            return

        result = process_webhook(payload)
        self._send_json(HTTPStatus.ACCEPTED, result)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        # Keep logs concise and machine-readable for deployments.
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} {format % args}")


def run_server() -> None:
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", "8000"))
    httpd = ThreadingHTTPServer((host, port), WebhookHandler)
    print(f"Listening on http://{host}:{port}/webhook")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
