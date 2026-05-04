"""Support ticket routes with AI pre-triage and notification hooks."""

from __future__ import annotations

from email.utils import parseaddr
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from threading import Lock
import time
from typing import Any, Dict, Tuple
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from flask import Blueprint, current_app, jsonify, request
from werkzeug.datastructures import FileStorage

from ..auth import get_current_user
from ..security_url import (
    assert_github_api_url,
    assert_resend_https_url,
    assert_slack_incoming_webhook_url,
    sanitize_header_value,
)


support_bp = Blueprint("support", __name__, url_prefix="/api/v1/support")
TICKET_REF_PATTERN = re.compile(r"\bHD-\d{8}(?:-\d+){1,2}\b", flags=re.IGNORECASE)
_HEADER_NAME_TOKEN_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
TICKET_SUBJECT_MAX_LENGTH = 24
TICKET_BODY_MAX_LENGTH = 2000
TICKET_EMAIL_MAX_LENGTH = 320

ALLOWED_TICKET_CATEGORIES = {
    "general": "General",
    "bug_report": "Bug Report",
    "account_issue": "Account Issue",
    "payment_issue": "Payment Issue",
    "business_relationship": "Business Relationship",
    "legal": "Legal",
}

AUTO_CATEGORY_TO_KEY = {
    "general": "general",
    "bug": "bug_report",
    "account": "account_issue",
    "billing": "payment_issue",
    "security": "legal",
}
ALLOWED_BUG_SURFACES = {"website", "app"}
ALLOWED_BUG_SEVERITIES = {"low", "medium", "high", "very_high"}
ALLOWED_BUG_REPRODUCIBLE = {"yes", "no"}
ALLOWED_PAYMENT_CHAINS = {
    "ethereum",
    "bsc",
    "tron",
    "solana",
    "bitcoin",
    "polygon",
    "arbitrum",
    "optimism",
    "avalanche",
    "base",
    "other",
}
PAYMENT_CHAIN_ALIASES = {
    "eth": "ethereum",
    "erc20": "ethereum",
    "bep20": "bsc",
    "trx": "tron",
    "trc20": "tron",
    "sol": "solana",
    "btc": "bitcoin",
    "matic": "polygon",
    "avax": "avalanche",
}
PAYMENT_TXID_MAX_LENGTH = 180
PAYMENT_TXID_PATTERN = re.compile(r"^[A-Za-z0-9._:/+\-=]{6,180}$")
ALLOWED_ATTACHMENT_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "heic",
    "mp4",
    "mov",
    "wmv",
}
PDF_DANGEROUS_MARKERS = ("/javascript", "/js", "/openaction", "/launch", "/embeddedfile")
SUSPICIOUS_TEXT_MARKERS = ("<script", "powershell", "cmd.exe", "bash -c", "curl http", "wget http", "drop table")
HEIC_BRANDS = {"heic", "heix", "hevc", "hevx", "mif1", "msf1"}
MP4_BRANDS = {"isom", "iso2", "mp41", "mp42", "avc1", "dash", "hvc1", "hev1"}
MOV_BRANDS = {"qt  "}
WMV_ASF_HEADER = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
GITHUB_PR_URL_PATTERN = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([0-9]+)",
    flags=re.IGNORECASE,
)
_SLACK_EVENT_CACHE: Dict[str, Dict[str, Any]] = {}
_SLACK_EVENT_CACHE_LOCK = Lock()
_SLACK_EVENT_CACHE_MAX_ENTRIES = 2048


def _sanitize_filename(name: str, *, default_name: str = "attachment") -> str:
    cleaned = os.path.basename(str(name or "").strip().replace("\\", "/"))
    if not cleaned:
        cleaned = default_name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._")
    if not cleaned:
        cleaned = default_name
    if len(cleaned) > 180:
        root, ext = os.path.splitext(cleaned)
        cleaned = f"{root[:160]}{ext[:12]}"
    return cleaned


def _attachment_extension(filename: str) -> str:
    _, ext = os.path.splitext(str(filename or "").strip().lower())
    return ext.lstrip(".")


def _printable_ratio(sample: bytes) -> float:
    if not sample:
        return 0.0
    printable = sum(1 for ch in sample if 9 <= ch <= 13 or 32 <= ch <= 126)
    return float(printable) / float(len(sample))


def _detect_attachment_signature(*, ext: str, head: bytes) -> Tuple[bool, str, str]:
    normalized_ext = str(ext or "").strip().lower()
    if normalized_ext in {"jpg", "jpeg"}:
        if head.startswith(b"\xff\xd8\xff"):
            return True, "image/jpeg", ""
        return False, "", "invalid_jpeg_signature"
    if normalized_ext == "png":
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return True, "image/png", ""
        return False, "", "invalid_png_signature"
    if normalized_ext == "pdf":
        if head.startswith(b"%PDF-"):
            return True, "application/pdf", ""
        return False, "", "invalid_pdf_signature"
    if normalized_ext == "heic":
        if len(head) >= 12 and head[4:8] == b"ftyp":
            brand = head[8:12].decode("latin1", errors="ignore").lower()
            if brand in HEIC_BRANDS:
                return True, "image/heic", ""
        return False, "", "invalid_heic_signature"
    if normalized_ext in {"mp4", "mov"}:
        if len(head) >= 12 and head[4:8] == b"ftyp":
            brand = head[8:12].decode("latin1", errors="ignore").lower()
            if normalized_ext == "mp4" and brand in MP4_BRANDS:
                return True, "video/mp4", ""
            if normalized_ext == "mov" and brand in MOV_BRANDS:
                return True, "video/quicktime", ""
        return False, "", f"invalid_{normalized_ext}_signature"
    if normalized_ext == "wmv":
        if head.startswith(WMV_ASF_HEADER):
            return True, "video/x-ms-wmv", ""
        return False, "", "invalid_wmv_signature"
    return False, "", "unsupported_extension"


def _run_optional_clamav_scan(*, file_path: str, timeout_seconds: int = 20) -> Dict[str, Any]:
    clamscan_bin = shutil.which("clamscan")
    if not clamscan_bin:
        return {"engine": "clamav", "status": "skipped", "detail": "clamscan_not_found"}
    try:
        proc = subprocess.run(
            [clamscan_bin, "--no-summary", file_path],
            capture_output=True,
            text=True,
            timeout=max(5, int(timeout_seconds)),
            check=False,
        )
    except Exception as exc:
        current_app.logger.exception("clamav_scan_failed: %s", exc)
        return {"engine": "clamav", "status": "error", "detail": "clamav_scan_failed"}
    detail = " ".join(str(proc.stdout or "").split())
    if proc.returncode == 0:
        return {"engine": "clamav", "status": "clean", "detail": detail}
    if proc.returncode == 1:
        return {"engine": "clamav", "status": "infected", "detail": detail or "infected"}
    return {
        "engine": "clamav",
        "status": "error",
        "detail": detail or str(proc.stderr or "").strip() or f"exit_code_{proc.returncode}",
    }


def _scan_and_stage_attachment(
    *,
    upload: FileStorage,
    max_bytes: int,
    use_clamav: bool,
) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None, int | None]:
    original_filename = _sanitize_filename(str(getattr(upload, "filename", "") or "attachment"))
    ext = _attachment_extension(original_filename)
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        return (
            None,
            {
                "error": "invalid_attachment_type",
                "message": f"Unsupported attachment type: {ext or 'unknown'}",
                "filename": original_filename,
            },
            400,
        )

    tmp_fd, tmp_path = tempfile.mkstemp(prefix="ticket_upload_", suffix=f".{ext}")
    os.close(tmp_fd)

    def fail(error_payload: Dict[str, Any], status_code: int) -> Tuple[None, Dict[str, Any], int]:
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return None, error_payload, status_code

    hasher = hashlib.sha256()
    size_bytes = 0
    head = b""
    text_probe = b""
    try:
        stream = getattr(upload, "stream", None)
        if stream is None:
            raise RuntimeError("upload_stream_missing")
        try:
            stream.seek(0)
        except Exception:
            pass
        with open(tmp_path, "wb") as out:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8", errors="ignore")
                if not isinstance(chunk, (bytes, bytearray)):
                    raise RuntimeError("invalid_upload_chunk")
                data = bytes(chunk)
                size_bytes += len(data)
                if size_bytes > max_bytes:
                    return fail(
                        {
                            "error": "attachment_too_large",
                            "message": f"Attachment exceeds limit of {max_bytes} bytes",
                            "filename": original_filename,
                        },
                        400,
                    )
                if len(head) < 64:
                    need = 64 - len(head)
                    head += data[:need]
                if len(text_probe) < 512 * 1024:
                    need_probe = (512 * 1024) - len(text_probe)
                    text_probe += data[:need_probe]
                hasher.update(data)
                out.write(data)
    except Exception as exc:
        current_app.logger.exception("attachment_read_failed: %s", exc)
        return fail(
            {
                "error": "attachment_read_failed",
                "message": "Unable to read attachment payload",
                "filename": original_filename,
                "detail": "attachment_read_failed",
            },
            400,
        )

    if size_bytes <= 0:
        return fail(
            {"error": "empty_attachment", "message": "Attachment cannot be empty", "filename": original_filename},
            400,
        )

    signature_ok, mime_type, signature_error = _detect_attachment_signature(ext=ext, head=head)
    if not signature_ok:
        return fail(
            {
                "error": "invalid_attachment_signature",
                "message": "Attachment signature does not match the declared file type",
                "filename": original_filename,
                "detail": signature_error,
            },
            400,
        )

    probe_text = text_probe.decode("latin1", errors="ignore").lower()
    if ext == "pdf":
        if any(marker in probe_text for marker in PDF_DANGEROUS_MARKERS):
            return fail(
                {
                    "error": "attachment_blocked",
                    "message": "PDF contains active content and was blocked",
                    "filename": original_filename,
                    "detail": "pdf_active_content_detected",
                },
                400,
            )
    elif _printable_ratio(text_probe[:64 * 1024]) > 0.96 and any(
        marker in probe_text for marker in SUSPICIOUS_TEXT_MARKERS
    ):
        return fail(
            {
                "error": "attachment_blocked",
                "message": "Attachment contains suspicious executable/script patterns",
                "filename": original_filename,
                "detail": "suspicious_text_markers_detected",
            },
            400,
        )

    clamav_result = {"engine": "clamav", "status": "disabled", "detail": "disabled"}
    scan_engine = "local_heuristics"
    if use_clamav:
        clamav_result = _run_optional_clamav_scan(file_path=tmp_path)
        if clamav_result.get("status") == "infected":
            return fail(
                {
                    "error": "attachment_infected",
                    "message": "Attachment blocked by malware scan",
                    "filename": original_filename,
                    "detail": str(clamav_result.get("detail") or "infected"),
                },
                400,
            )
        if clamav_result.get("status") == "error":
            return fail(
                {
                    "error": "attachment_scan_failed",
                    "message": "Attachment security scan failed; please retry later",
                    "filename": original_filename,
                    "detail": str(clamav_result.get("detail") or "clamav_error"),
                },
                503,
            )
        if clamav_result.get("status") == "clean":
            scan_engine = "clamav+heuristics"

    stored_filename = f"{int(time.time())}-{secrets.token_hex(10)}.{ext}"
    return (
        {
            "tmp_path": tmp_path,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "sha256": hasher.hexdigest(),
            "scan_engine": scan_engine,
            "scan_result": "clean",
            "scan_details": {
                "signature": "ok",
                "clamav": clamav_result,
            },
        },
        None,
        None,
    )


def _cleanup_staged_attachments(staged: list[Dict[str, Any]]) -> None:
    for item in staged:
        tmp_path = str(item.get("tmp_path", "")).strip()
        if not tmp_path:
            continue
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except Exception:
            continue


def _persist_staged_attachments(
    *,
    staged: list[Dict[str, Any]],
    ticket_ref: str,
    attachments_dir: str,
    ticket_store: Any,
) -> list[Dict[str, Any]]:
    base_dir = os.path.abspath(str(attachments_dir or "").strip() or os.path.join(current_app.instance_path, "support_attachments"))
    os.makedirs(base_dir, exist_ok=True)
    ticket_dir = os.path.abspath(os.path.join(base_dir, ticket_ref))
    if os.path.commonpath([base_dir, ticket_dir]) != base_dir:
        raise RuntimeError("invalid_attachment_storage_path")
    os.makedirs(ticket_dir, exist_ok=True)

    persisted: list[Dict[str, Any]] = []
    for item in staged:
        stored_filename = str(item.get("stored_filename", "")).strip()
        if not stored_filename:
            raise RuntimeError("invalid_stored_filename")
        tmp_path = str(item.get("tmp_path", "")).strip()
        if not tmp_path or not os.path.isfile(tmp_path):
            raise RuntimeError("missing_staged_attachment")
        destination = os.path.abspath(os.path.join(ticket_dir, stored_filename))
        if os.path.commonpath([ticket_dir, destination]) != ticket_dir:
            raise RuntimeError("unsafe_attachment_destination")
        os.replace(tmp_path, destination)
        rel_path = os.path.relpath(destination, base_dir).replace("\\", "/")
        created = ticket_store.add_ticket_attachment(
            ticket_ref=ticket_ref,
            original_filename=str(item.get("original_filename", "")).strip(),
            stored_filename=stored_filename,
            storage_rel_path=rel_path,
            mime_type=str(item.get("mime_type", "")).strip(),
            size_bytes=int(item.get("size_bytes") or 0),
            sha256=str(item.get("sha256", "")).strip(),
            scan_engine=str(item.get("scan_engine", "")).strip(),
            scan_result=str(item.get("scan_result", "")).strip(),
            scan_details=item.get("scan_details"),
        )
        if created is None:
            raise RuntimeError("attachment_store_insert_failed")
        persisted.append(created)
    return persisted


def _record_operational_alert(
    *,
    category: str,
    severity: str,
    message: str,
    event_key: str = "",
    context: Dict[str, Any] | None = None,
) -> None:
    try:
        store = current_app.config.get("SUPPORT_TICKET_STORE")
        if store is None:
            return
        store.create_operational_alert(
            category=category,
            severity=severity,
            message=message,
            event_key=event_key,
            context=context or {},
        )
    except Exception:  # pragma: no cover - defensive guard
        current_app.logger.exception("operational_alert_store_failed category=%s event_key=%s", category, event_key)


def _notify_support_slack(
    *,
    event: str,
    ticket: Dict[str, Any],
    sender_email: str = "",
    message_body: str = "",
    source: str = "web_portal",
) -> None:
    notifier = current_app.config.get("SUPPORT_SLACK_NOTIFIER")
    if notifier is None:
        return

    result: Dict[str, Any] | None = None
    if getattr(notifier, "configured", False):
        try:
            if event == "new_ticket":
                result = notifier.notify_new_ticket(ticket=ticket, source=source)
            elif event == "customer_reply":
                result = notifier.notify_customer_reply(
                    ticket=ticket,
                    sender_email=sender_email or str(ticket.get("customer_email", "")),
                    message_body=message_body,
                    via=source,
                )
            else:
                return
        except Exception as exc:  # pragma: no cover - defensive guard
            _record_operational_alert(
                category="support_notify",
                severity="warning",
                message="Slack notification failed due to internal exception",
                event_key=f"slack_notify_exception:{event}:{ticket.get('ticket_ref', '')}",
                context={"event": event, "ticket_ref": ticket.get("ticket_ref"), "error": type(exc).__name__},
            )
            return

        if result and not result.get("sent"):
            _record_operational_alert(
                category="support_notify",
                severity="warning",
                message="Slack notification delivery failed",
                event_key=f"slack_notify_failed:{event}:{ticket.get('ticket_ref', '')}",
                context={
                    "event": event,
                    "ticket_ref": ticket.get("ticket_ref"),
                    "sender_email": sender_email,
                    "error": str(result.get("error", "unknown_error")),
                    "detail": str(result.get("detail", "")),
                },
            )

    # Bug Report automation: forward a Cursor-tagged implementation prompt
    # to the dedicated #github_pull_requests webhook/channel.
    if event == "new_ticket" and str(ticket.get("category", "")).strip().lower() == "bug report":
        if not getattr(notifier, "bug_cursor_enabled", False):
            return
        try:
            cursor_result = notifier.notify_bug_report_to_cursor(
                ticket=ticket,
                message_body=message_body or str(ticket.get("message", "")),
                source=source,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            _record_operational_alert(
                category="support_notify",
                severity="warning",
                message="Bug report Cursor relay failed due to internal exception",
                event_key=f"bug_cursor_exception:{ticket.get('ticket_ref', '')}",
                context={"ticket_ref": ticket.get("ticket_ref"), "error": type(exc).__name__},
            )
            return
        if str(cursor_result.get("error", "")).strip().lower() == "bug_report_blocked_untrusted_payload":
            _record_operational_alert(
                category="support_notify",
                severity="critical",
                message="Bug report automation blocked due to untrusted payload pattern",
                event_key=f"bug_cursor_blocked:{ticket.get('ticket_ref', '')}",
                context={
                    "ticket_ref": ticket.get("ticket_ref"),
                    "risk_signals": cursor_result.get("risk_signals") or [],
                    "source": source,
                },
            )
            return
        if not bool(cursor_result.get("sent")):
            _record_operational_alert(
                category="support_notify",
                severity="warning",
                message="Bug report Cursor relay delivery failed",
                event_key=f"bug_cursor_failed:{ticket.get('ticket_ref', '')}",
                context={
                    "ticket_ref": ticket.get("ticket_ref"),
                    "error": str(cursor_result.get("error", "unknown_error")),
                    "detail": str(cursor_result.get("detail", "")),
                },
            )


def _short_text(value: str, *, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "..."


def _run_above_unmapped_threshold(run: Dict[str, Any], *, threshold: int) -> bool:
    if int(threshold or 0) <= 0:
        return False
    checked = int(run.get("checked") or 0)
    unmapped = int(run.get("unmapped") or 0)
    return checked > 0 and unmapped >= int(threshold)


def _recent_runs_have_sustained_breach(
    runs: list[Dict[str, Any]],
    *,
    threshold: int,
    consecutive_runs: int,
) -> bool:
    required = max(1, int(consecutive_runs or 0))
    if len(runs) < required:
        return False
    for row in runs[:required]:
        if not _run_above_unmapped_threshold(row, threshold=threshold):
            return False
    return True


def _post_slack_webhook(*, webhook_url: str, timeout_seconds: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    target = str(webhook_url or "").strip()
    if not target:
        return {"sent": False, "error": "slack_webhook_missing"}
    try:
        assert_slack_incoming_webhook_url(target)
    except ValueError as exc:
        current_app.logger.warning("slack_webhook_rejected: %s", exc)
        return {"sent": False, "error": "slack_webhook_invalid"}

    req = urlrequest.Request(
        target,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "HodlerSuiteWebhookRelay/1.0",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=max(3, int(timeout_seconds))) as response:
            status = int(getattr(response, "status", 0) or 0)
            if 200 <= status < 300:
                return {"sent": True, "status": status}
            return {"sent": False, "error": f"slack_http_{status}"}
    except urlerror.HTTPError as exc:  # pragma: no cover - network dependency
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return {
            "sent": False,
            "error": f"slack_http_{exc.code}",
            "detail": _short_text(detail, limit=320),
        }
    except Exception as exc:  # pragma: no cover - network dependency
        current_app.logger.exception("slack_webhook_post_failed: %s", exc)
        return {"sent": False, "error": "slack_webhook_post_failed"}


def _simple_triage(subject: str, message: str):
    text = f"{subject} {message}".lower()
    if any(token in text for token in ["payment", "invoice", "subscription", "refund"]):
        return "billing", 0.76
    if any(token in text for token in ["hack", "breach", "phishing", "stolen", "compromised"]):
        return "security", 0.79
    if any(token in text for token in ["bug", "error", "crash", "timeout", "exception"]):
        return "bug", 0.72
    if any(token in text for token in ["login", "password", "2fa", "account", "email"]):
        return "account", 0.68
    return "general", 0.51


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _is_valid_email(value: str) -> bool:
    candidate = str(value or "").strip()
    if not candidate or len(candidate) > TICKET_EMAIL_MAX_LENGTH:
        return False
    parsed = str(parseaddr(candidate)[1] or "").strip()
    if not parsed or parsed != candidate:
        return False
    if parsed.count("@") != 1:
        return False
    local_part, domain_part = parsed.rsplit("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return False
    return True


def _extract_text_payload(payload: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_sender_email(payload: Dict[str, Any]) -> str:
    for key in ("from", "from_email", "sender", "reply_to", "replyTo"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidate = str(value.get("email", "")).strip()
        else:
            candidate = str(value or "").strip()
        if not candidate:
            continue
        _, parsed = parseaddr(candidate)
        email = parsed or candidate
        normalized = _normalize_email(email)
        if "@" in normalized and "." in normalized:
            return normalized
    return ""


def _strip_html(html_text: str) -> str:
    if not html_text:
        return ""
    raw = str(html_text)
    if len(raw) > 256 * 1024:
        raw = raw[: 256 * 1024]
    no_script = re.sub(r"(?is)<script\b[^>]*>.*?</script\b[^>]*>", " ", raw)
    no_script = re.sub(r"(?is)<style\b[^>]*>.*?</style\b[^>]*>", " ", no_script)
    no_tags = re.sub(r"(?is)<[^>]{0,2000}>", " ", no_script)
    collapsed = re.sub(r"[ \t]+", " ", no_tags)
    return collapsed.strip()


def _extract_message_body(payload: Dict[str, Any]) -> str:
    text = _extract_text_payload(payload, "text", "text_body", "body_text", "plain", "body")
    if text:
        return text
    html_text = _extract_text_payload(payload, "html", "html_body", "body_html")
    return _strip_html(html_text)


def _trim_quoted_content(message: str) -> str:
    if not message:
        return ""
    cut_markers = (
        "--- original message ---",
        "---------- forwarded message ----------",
        "from:",
    )
    lines = []
    for line in str(message).splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped.startswith(">"):
            break
        if lowered.startswith("on ") and " wrote:" in lowered:
            break
        if any(lowered.startswith(marker) for marker in cut_markers):
            break
        lines.append(line)
    result = "\n".join(lines).strip()
    return result if result else str(message).strip()


def _extract_first_email(text: str) -> str:
    if not text:
        return ""
    raw = str(text)
    if len(raw) > 32768:
        raw = raw[:32768]
    match = re.search(
        r"\b[A-Z0-9._%+-]{1,320}@[A-Z0-9.-]{1,255}\.[A-Z]{2,63}\b",
        raw,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return _normalize_email(match.group(1))


def _extract_forwarded_sender(raw_message: str, *, subject: str = "") -> str:
    if not raw_message:
        return ""
    subj = str(subject or "")[:4096]
    body = str(raw_message)
    if len(body) > 65536:
        body = body[:65536]
    forwarded_hints = ("fwd:", "fw:", "forwarded message", "ha scritto:", "\nfrom:")
    lowered = f"{subj}\n{body}".lower()
    if not any(hint in lowered for hint in forwarded_hints):
        return ""

    from_line = re.search(
        r"(?im)^\s*from:\s*(?:[^<\r\n]{0,256}<)?([A-Z0-9._%+-]{1,320}@[A-Z0-9.-]{1,255}\.[A-Z]{2,63})",
        body,
    )
    if from_line:
        return _normalize_email(from_line.group(1))
    return _extract_first_email(raw_message)


def _extract_ticket_ref(payload: Dict[str, Any], *, subject: str, message: str) -> str:
    candidates = [
        subject,
        message,
        _extract_text_payload(payload, "to", "recipient", "envelope_to"),
    ]
    for candidate in candidates:
        match = TICKET_REF_PATTERN.search(str(candidate or ""))
        if match:
            return match.group(0).upper()
    return ""


def _extract_client_ip() -> str:
    cf_ip = str(request.headers.get("CF-Connecting-IP", "")).strip()
    if cf_ip:
        return cf_ip

    forwarded = str(request.headers.get("X-Forwarded-For", "")).strip()
    if forwarded:
        return forwarded.split(",")[0].strip()

    return str(request.remote_addr or "").strip() or "unknown"


def _is_support_sender(email: str) -> bool:
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return False

    settings = current_app.config["SETTINGS"]
    support_candidates = set()

    for raw in str(settings.support_email_notify_to or "").split(","):
        candidate = _normalize_email(raw)
        if candidate:
            support_candidates.add(candidate)

    for raw in str(settings.support_email_from or "").split(","):
        candidate = _normalize_email(raw)
        if candidate:
            support_candidates.add(candidate)

    for raw in settings.support_agent_emails or []:
        candidate = _normalize_email(raw)
        if candidate:
            support_candidates.add(candidate)

    return normalized_email in support_candidates


def _extract_supplied_secret() -> str:
    return _extract_secret_from_request("X-Support-Inbound-Secret")


def _extract_secret_from_request(*header_names: str, query_name: str = "secret") -> str:
    for header_name in header_names:
        supplied_secret = str(request.headers.get(header_name, "")).strip()
        if supplied_secret:
            return supplied_secret

    supplied_secret = str(request.args.get(query_name, "")).strip()
    if supplied_secret:
        return supplied_secret

    auth_header = str(request.headers.get("Authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return ""


def _authorize_inbound_webhook() -> Tuple[bool, Dict[str, Any], int]:
    settings = current_app.config["SETTINGS"]
    configured_secret = str(settings.support_inbound_webhook_secret or "").strip()
    if not configured_secret:
        return False, {"error": "inbound_webhook_not_configured"}, 503

    supplied_secret = _extract_supplied_secret()
    if not supplied_secret or not secrets.compare_digest(supplied_secret, configured_secret):
        return False, {"error": "unauthorized"}, 401

    return True, {}, 200


def _extract_nested_value(payload: Dict[str, Any], *paths: Tuple[str, ...]) -> str:
    for path in paths:
        value: Any = payload
        valid_path = True
        for key in path:
            if not isinstance(value, dict):
                valid_path = False
                break
            value = value.get(key)
        if not valid_path:
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _format_trustpilot_stars(payload: Dict[str, Any]) -> str:
    raw = _extract_nested_value(
        payload,
        ("stars",),
        ("rating",),
        ("score",),
        ("review", "stars"),
        ("review", "rating"),
        ("data", "stars"),
        ("data", "rating"),
    )
    if not raw:
        return ""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return raw
    if value.is_integer():
        return f"{int(value)}/5"
    return f"{value:.1f}/5"


def _build_trustpilot_event_id(payload: Dict[str, Any]) -> str:
    event_id = _extract_nested_value(
        payload,
        ("eventId",),
        ("event_id",),
        ("id",),
        ("review", "id"),
        ("data", "id"),
        ("resource", "id"),
    )
    if event_id:
        return event_id

    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"tp-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]}"


def _ingest_inbound_email_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    sender_email = _extract_sender_email(payload)
    subject = _extract_text_payload(payload, "subject", "email_subject")
    raw_message = _extract_message_body(payload)
    message = _trim_quoted_content(raw_message)
    ticket_ref = _extract_ticket_ref(payload, subject=subject, message=message)

    if not sender_email:
        return {"error": "invalid_payload", "message": "sender email is required"}, 400
    if not ticket_ref:
        return {"error": "invalid_payload", "message": "ticket reference not found in subject/body"}, 400
    if not message:
        return {"error": "invalid_payload", "message": "message body is required"}, 400

    store = current_app.config["SUPPORT_TICKET_STORE"]
    ticket = store.get_ticket_by_ref(ticket_ref)
    if not ticket:
        return {"error": "ticket_not_found", "ticket_id": ticket_ref}, 404

    author_type = "support" if _is_support_sender(sender_email) else "customer"
    forwarded_sender = _extract_forwarded_sender(raw_message, subject=subject)
    if author_type == "support" and forwarded_sender and not _is_support_sender(forwarded_sender):
        author_type = "customer"
        sender_email = forwarded_sender
    mailer = current_app.config["SUPPORT_MAILER"]
    email_delivery: Dict[str, Any] = {}

    if author_type == "support":
        relay = mailer.send_agent_reply(
            ticket=ticket,
            reply_body=message,
            agent_email=sender_email,
        )
        email_delivery["customer_relay"] = "sent" if relay.get("sent") else "failed"
        if not relay.get("sent"):
            email_delivery["customer_relay_error"] = str(relay.get("error", "unknown_error"))
            _record_operational_alert(
                category="support_relay",
                severity="error",
                message="Support reply relay to customer failed",
                event_key=f"relay:{ticket_ref}:{sender_email}",
                context={
                    "ticket_ref": ticket_ref,
                    "sender_email": sender_email,
                    "relay_error": email_delivery["customer_relay_error"],
                },
            )
            return {
                "error": "relay_send_failed",
                "message": "support reply ingested but customer relay failed",
                "ticket_id": ticket_ref,
                "from": sender_email,
                "author_type": author_type,
                "email_delivery": email_delivery,
            }, 502

    if not store.add_ticket_message(
        ticket_ref=ticket_ref,
        author_type=author_type,
        author_email=sender_email,
        body=message,
    ):
        _record_operational_alert(
            category="ticket_store",
            severity="critical",
            message="Inbound message could not be stored",
            event_key=f"message_not_stored:{ticket_ref}:{sender_email}",
            context={
                "ticket_ref": ticket_ref,
                "sender_email": sender_email,
                "author_type": author_type,
            },
        )
        return {"error": "message_not_stored"}, 500

    current_status = str(ticket.get("status", "")).strip().lower()
    if current_status != "in_progress" and author_type in {"customer", "support"}:
        store.set_ticket_status(ticket_ref=ticket_ref, status="in_progress")

    if author_type == "customer":
        support_update = mailer.send_customer_followup_notification(ticket=ticket, message_body=message)
        email_delivery["support_update"] = "sent" if support_update.get("sent") else "failed"
        if not support_update.get("sent"):
            email_delivery["support_update_error"] = str(support_update.get("error", "unknown_error"))
            _record_operational_alert(
                category="support_notify",
                severity="warning",
                message="Support follow-up notification failed after customer reply",
                event_key=f"support_update:{ticket_ref}",
                context={
                    "ticket_ref": ticket_ref,
                    "sender_email": sender_email,
                    "error": email_delivery["support_update_error"],
                },
            )
        _notify_support_slack(
            event="customer_reply",
            ticket=ticket,
            sender_email=sender_email,
            message_body=message,
            source="inbound_email",
        )

    return {
        "status": "ingested",
        "ticket_id": ticket_ref,
        "from": sender_email,
        "author_type": author_type,
        "email_delivery": email_delivery,
    }, 201


def _stringify_recipients(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("email", "address", "name"):
            candidate = str(value.get(key, "")).strip()
            if candidate:
                return candidate
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            part = _stringify_recipients(item)
            if part:
                parts.append(part)
        return ", ".join(parts)
    return str(value or "").strip()


def _normalize_sender_value(value: Any) -> Any:
    if isinstance(value, list):
        if not value:
            return ""
        first = value[0]
        return first if isinstance(first, dict) else str(first).strip()
    return value


def _fetch_resend_received_email(*, email_id: str, api_key: str, timeout_seconds: int) -> Tuple[Dict[str, Any] | None, str | None]:
    email_id_quoted = urlparse.quote(email_id, safe="")
    endpoints = [
        f"https://api.resend.com/emails/receiving/{email_id_quoted}",
        f"https://api.resend.com/emails/{email_id_quoted}",
    ]
    base_headers = {
        "Accept": "application/json",
        # Resend is fronted by Cloudflare; an explicit UA avoids occasional bot-style HTML blocks.
        "User-Agent": "Mozilla/5.0 (compatible; HodlerSuiteSupport/1.0; +https://app.hodler-suite.com)",
    }
    auth_header_variants = [
        {"Authorization": f"Bearer {api_key}", "X-Api-Key": api_key},
        {"Authorization": f"Bearer {api_key}"},
        {"X-Api-Key": api_key},
    ]

    timeout = max(3, int(timeout_seconds))
    attempts = []

    for endpoint in endpoints:
        try:
            assert_resend_https_url(endpoint)
        except ValueError:
            attempts.append("resend_endpoint_blocked")
            continue
        for auth_headers in auth_header_variants:
            req = urlrequest.Request(endpoint, method="GET", headers={**base_headers, **auth_headers})
            raw_body = ""
            try:
                with urlrequest.urlopen(req, timeout=timeout) as response:
                    raw_body = response.read().decode("utf-8", "replace")
            except urlerror.HTTPError as exc:  # pragma: no cover - network dependency
                try:
                    raw_body = exc.read().decode("utf-8", "replace")
                except Exception:
                    raw_body = ""
                detail = f"{endpoint} -> resend_http_{exc.code}"
                if raw_body:
                    snippet = raw_body[:180]
                    if "<html" in raw_body.lower():
                        snippet = "html_response"
                    detail = f"{detail}: {snippet}"
                attempts.append(detail)
                continue
            except Exception as exc:  # pragma: no cover - network dependency
                attempts.append(f"{endpoint} -> resend_fetch_error: {exc}")
                continue

            try:
                decoded = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                attempts.append(f"{endpoint} -> resend_invalid_json")
                continue

            if isinstance(decoded, dict) and isinstance(decoded.get("data"), dict):
                decoded = decoded["data"]

            if isinstance(decoded, dict):
                return decoded, None
            attempts.append(f"{endpoint} -> resend_invalid_payload")

    if attempts:
        return None, "; ".join(attempts[:4])
    return None, "resend_fetch_failed"


def _list_resend_received_emails(*, api_key: str, timeout_seconds: int, limit: int = 20) -> Tuple[list[Dict[str, Any]], str | None]:
    endpoint = f"https://api.resend.com/emails/receiving?limit={max(1, min(int(limit), 100))}"
    base_headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; HodlerSuiteSupport/1.0; +https://app.hodler-suite.com)",
    }
    auth_header_variants = [
        {"Authorization": f"Bearer {api_key}", "X-Api-Key": api_key},
        {"Authorization": f"Bearer {api_key}"},
        {"X-Api-Key": api_key},
    ]

    timeout = max(3, int(timeout_seconds))
    attempts = []
    try:
        assert_resend_https_url(endpoint)
    except ValueError:
        return [], "resend_endpoint_blocked"
    for auth_headers in auth_header_variants:
        req = urlrequest.Request(endpoint, method="GET", headers={**base_headers, **auth_headers})
        raw_body = ""
        try:
            with urlrequest.urlopen(req, timeout=timeout) as response:
                raw_body = response.read().decode("utf-8", "replace")
        except urlerror.HTTPError as exc:  # pragma: no cover - network dependency
            try:
                raw_body = exc.read().decode("utf-8", "replace")
            except Exception:
                raw_body = ""
            detail = f"resend_http_{exc.code}"
            if raw_body:
                snippet = raw_body[:180]
                if "<html" in raw_body.lower():
                    snippet = "html_response"
                detail = f"{detail}: {snippet}"
            attempts.append(detail)
            continue
        except Exception as exc:  # pragma: no cover - network dependency
            attempts.append(f"resend_list_error:{exc}")
            continue

        try:
            decoded = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            attempts.append("resend_list_invalid_json")
            continue

        if not isinstance(decoded, dict):
            attempts.append("resend_list_invalid_payload")
            continue
        rows = decoded.get("data")
        if not isinstance(rows, list):
            attempts.append("resend_list_missing_data")
            continue
        normalized_rows = [row for row in rows if isinstance(row, dict)]
        return normalized_rows, None

    if attempts:
        return [], "; ".join(attempts[:4])
    return [], "resend_list_failed"


def _prune_slack_event_cache(*, now_epoch: int) -> None:
    with _SLACK_EVENT_CACHE_LOCK:
        stale_keys = [
            key
            for key, row in _SLACK_EVENT_CACHE.items()
            if int(row.get("expires_at_epoch", 0) or 0) <= now_epoch
        ]
        for stale in stale_keys:
            _SLACK_EVENT_CACHE.pop(stale, None)
        if len(_SLACK_EVENT_CACHE) <= _SLACK_EVENT_CACHE_MAX_ENTRIES:
            return
        oldest = sorted(
            _SLACK_EVENT_CACHE.items(),
            key=lambda item: int(item[1].get("expires_at_epoch", 0) or 0),
        )
        trim = len(_SLACK_EVENT_CACHE) - _SLACK_EVENT_CACHE_MAX_ENTRIES
        for key, _ in oldest[:trim]:
            _SLACK_EVENT_CACHE.pop(key, None)


def _is_duplicate_slack_event(event_id: str) -> bool:
    token = str(event_id or "").strip()
    if not token:
        return False
    now_epoch = int(time.time())
    _prune_slack_event_cache(now_epoch=now_epoch)
    with _SLACK_EVENT_CACHE_LOCK:
        row = _SLACK_EVENT_CACHE.get(token)
        if row and int(row.get("expires_at_epoch", 0) or 0) > now_epoch:
            return True
        _SLACK_EVENT_CACHE[token] = {"expires_at_epoch": now_epoch + 6 * 60 * 60}
    return False


def _verify_slack_events_signature(*, signing_secret: str, raw_body: bytes) -> bool:
    secret = str(signing_secret or "").strip()
    if not secret:
        return False
    supplied_signature = str(request.headers.get("X-Slack-Signature", "")).strip()
    supplied_timestamp = str(request.headers.get("X-Slack-Request-Timestamp", "")).strip()
    if not supplied_signature or not supplied_timestamp:
        return False
    try:
        ts_value = int(supplied_timestamp)
    except (TypeError, ValueError):
        return False
    now_epoch = int(time.time())
    # Slack recommends rejecting replay windows older than 5 minutes.
    if abs(now_epoch - ts_value) > 5 * 60:
        return False

    body_text = raw_body.decode("utf-8", errors="replace")
    base_string = f"v0:{supplied_timestamp}:{body_text}"
    computed = "v0=" + hmac.new(
        secret.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, supplied_signature)


def _slack_api_request(
    *,
    bot_token: str,
    api_method: str,
    query_params: Dict[str, Any] | None = None,
    form_params: Dict[str, Any] | None = None,
    timeout_seconds: int = 8,
) -> Dict[str, Any]:
    endpoint = f"https://slack.com/api/{str(api_method or '').strip()}"
    query = query_params or {}
    form = form_params or {}
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Accept": "application/json; charset=utf-8",
        "User-Agent": "HodlerSuiteSlackAutomation/1.0",
    }
    data: bytes | None = None
    method = "GET"
    if form:
        data = urlparse.urlencode({k: str(v) for k, v in form.items() if v is not None}).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
    if query:
        endpoint = f"{endpoint}?{urlparse.urlencode({k: str(v) for k, v in query.items() if v is not None})}"
    req = urlrequest.Request(endpoint, data=data, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=max(3, int(timeout_seconds))) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:  # pragma: no cover - network dependency
        return {"ok": False, "error": f"slack_api_request_failed:{exc}"}

    if not isinstance(payload, dict):
        return {"ok": False, "error": "slack_api_invalid_payload"}
    if not bool(payload.get("ok")):
        return {"ok": False, "error": str(payload.get("error") or "slack_api_error"), "payload": payload}
    return {"ok": True, "payload": payload}


def _extract_text_from_slack_message(message: Dict[str, Any]) -> str:
    parts: list[str] = []
    text = str(message.get("text", "")).strip()
    if text:
        parts.append(text)

    attachments = message.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            for key in ("title", "title_link", "text", "fallback"):
                value = str(attachment.get(key, "")).strip()
                if value:
                    parts.append(value)

    blocks = message.get("blocks")
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            text_payload = block.get("text")
            if isinstance(text_payload, dict):
                value = str(text_payload.get("text", "")).strip()
                if value:
                    parts.append(value)
            elements = block.get("elements")
            if isinstance(elements, list):
                for element in elements:
                    if not isinstance(element, dict):
                        continue
                    value = str(element.get("text", "")).strip()
                    if value:
                        parts.append(value)

    merged = "\n".join(item for item in parts if item)
    return merged.strip()


def _extract_github_pr_reference(text: str) -> Dict[str, Any] | None:
    raw = str(text or "")
    if not raw:
        return None
    match = GITHUB_PR_URL_PATTERN.search(raw)
    if not match:
        return None
    owner = str(match.group(1) or "").strip()
    repo = str(match.group(2) or "").strip()
    try:
        number = int(match.group(3))
    except (TypeError, ValueError):
        return None
    if not owner or not repo or number <= 0:
        return None
    return {
        "owner": owner,
        "repo": repo,
        "number": number,
        "url": str(match.group(0) or "").strip(),
    }


def _github_api_request(
    *,
    github_token: str,
    path: str,
    method: str = "GET",
    json_payload: Dict[str, Any] | None = None,
    timeout_seconds: int = 10,
) -> Dict[str, Any]:
    target = f"https://api.github.com{path}"
    try:
        assert_github_api_url(target)
    except ValueError:
        return {"ok": False, "error": "github_api_url_invalid"}
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "HodlerSuiteSlackAutomation/1.0",
    }
    data = None
    if json_payload is not None:
        data = json.dumps(json_payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urlrequest.Request(target, data=data, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=max(3, int(timeout_seconds))) as response:
            status = int(getattr(response, "status", 0) or 0)
            raw_body = response.read().decode("utf-8", "replace")
    except urlerror.HTTPError as exc:  # pragma: no cover - network dependency
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return {"ok": False, "status": int(exc.code), "error": f"github_http_{exc.code}", "detail": _short_text(detail, limit=360)}
    except Exception as exc:  # pragma: no cover - network dependency
        return {"ok": False, "error": f"github_request_failed:{exc}"}

    payload: Dict[str, Any] = {}
    if raw_body:
        try:
            decoded = json.loads(raw_body)
            if isinstance(decoded, dict):
                payload = decoded
        except json.JSONDecodeError:
            payload = {}
    if 200 <= status < 300:
        return {"ok": True, "status": status, "payload": payload}
    return {"ok": False, "status": status, "error": f"github_http_{status}", "payload": payload}


def _process_github_pr_approval_reaction(*, event: Dict[str, Any]) -> Dict[str, Any]:
    settings = current_app.config["SETTINGS"]
    reaction_raw = str(event.get("reaction", "")).strip().lower()
    reaction_aliases = {
        "white_check_mark": "white_check_mark",
        "heavy_check_mark": "white_check_mark",
        "check_mark": "white_check_mark",
        "no_entry": "no_entry",
        "no_entry_sign": "no_entry",
        "stop_sign": "no_entry",
    }
    reaction = reaction_aliases.get(reaction_raw, reaction_raw)
    if reaction not in {"white_check_mark", "no_entry"}:
        return {"status": "ignored", "reason": "reaction_not_supported"}

    item = event.get("item")
    if not isinstance(item, dict):
        return {"status": "ignored", "reason": "missing_item"}
    channel_id = str(item.get("channel", "")).strip()
    message_ts = str(item.get("ts", "")).strip()
    reactor_user_id = str(event.get("user", "")).strip()
    if not channel_id or not message_ts or not reactor_user_id:
        return {"status": "ignored", "reason": "missing_reaction_fields"}

    restricted_channel = str(getattr(settings, "slack_github_pull_requests_channel_id", "") or "").strip()
    if restricted_channel and channel_id != restricted_channel:
        return {"status": "ignored", "reason": "channel_not_allowed"}

    allowed_reactors = {str(item).strip() for item in (settings.slack_github_approver_user_ids or []) if str(item).strip()}
    if allowed_reactors and reactor_user_id not in allowed_reactors:
        return {"status": "ignored", "reason": "reactor_not_allowed"}

    slack_bot_token = str(getattr(settings, "slack_bot_token", "") or "").strip()
    github_token = str(getattr(settings, "github_token", "") or "").strip()
    if not slack_bot_token or not github_token:
        return {"status": "error", "error": "missing_slack_or_github_token"}

    history = _slack_api_request(
        bot_token=slack_bot_token,
        api_method="conversations.history",
        query_params={
            "channel": channel_id,
            "latest": message_ts,
            "inclusive": "true",
            "limit": "1",
        },
        timeout_seconds=8,
    )
    if not bool(history.get("ok")):
        return {"status": "error", "error": str(history.get("error") or "slack_history_failed")}

    history_payload = history.get("payload")
    messages = history_payload.get("messages") if isinstance(history_payload, dict) else None
    if not isinstance(messages, list) or not messages:
        return {"status": "ignored", "reason": "message_not_found"}

    message = messages[0] if isinstance(messages[0], dict) else {}
    message_text = _extract_text_from_slack_message(message)
    pr = _extract_github_pr_reference(message_text)
    if not pr:
        return {"status": "ignored", "reason": "github_pr_link_not_found"}

    owner = str(pr.get("owner", "")).strip()
    repo = str(pr.get("repo", "")).strip()
    number = int(pr.get("number") or 0)
    pr_url = str(pr.get("url", "")).strip()
    configured_owner = str(getattr(settings, "github_owner", "") or "").strip()
    configured_repo = str(getattr(settings, "github_repo", "") or "").strip()
    if configured_owner and configured_owner.lower() != owner.lower():
        return {"status": "ignored", "reason": "github_owner_mismatch"}
    if configured_repo and configured_repo.lower() != repo.lower():
        return {"status": "ignored", "reason": "github_repo_mismatch"}

    pr_details = _github_api_request(
        github_token=github_token,
        path=f"/repos/{owner}/{repo}/pulls/{number}",
        method="GET",
        timeout_seconds=10,
    )
    if not bool(pr_details.get("ok")):
        return {
            "status": "error",
            "error": "github_pr_read_failed",
            "detail": str(pr_details.get("error") or ""),
            "pr_url": pr_url,
        }
    pr_payload = pr_details.get("payload") if isinstance(pr_details.get("payload"), dict) else {}
    if str(pr_payload.get("state", "")).strip().lower() != "open":
        return {"status": "ignored", "reason": "pr_not_open", "pr_url": pr_url}
    if bool(pr_payload.get("draft")):
        return {"status": "ignored", "reason": "pr_is_draft", "pr_url": pr_url}
    head_ref = str(((pr_payload.get("head") or {}).get("ref") if isinstance(pr_payload.get("head"), dict) else "") or "").strip()
    base_ref = str(((pr_payload.get("base") or {}).get("ref") if isinstance(pr_payload.get("base"), dict) else "") or "").strip()

    if reaction == "no_entry":
        review_result = _github_api_request(
            github_token=github_token,
            path=f"/repos/{owner}/{repo}/pulls/{number}/reviews",
            method="POST",
            json_payload={
                "event": "REQUEST_CHANGES",
                "body": f"Requested changes from Slack reaction :no_entry: by <@{reactor_user_id}>.",
            },
            timeout_seconds=10,
        )
        close_result = _github_api_request(
            github_token=github_token,
            path=f"/repos/{owner}/{repo}/pulls/{number}",
            method="PATCH",
            json_payload={"state": "closed"},
            timeout_seconds=10,
        )
        if not bool(close_result.get("ok")):
            return {
                "status": "error",
                "error": "github_pr_close_failed",
                "detail": str(close_result.get("error") or ""),
                "pr_url": pr_url,
                "review_result": review_result,
            }
        ack_text = f"⛔ PR closed via Slack reaction by <@{reactor_user_id}>: {pr_url}"
        _slack_api_request(
            bot_token=slack_bot_token,
            api_method="chat.postMessage",
            form_params={
                "channel": channel_id,
                "thread_ts": message_ts,
                "text": ack_text,
            },
            timeout_seconds=8,
        )
        return {
            "status": "processed",
            "pr_url": pr_url,
            "approved": False,
            "closed": True,
            "merged": False,
            "reactor_user_id": reactor_user_id,
        }

    approve = _github_api_request(
        github_token=github_token,
        path=f"/repos/{owner}/{repo}/pulls/{number}/reviews",
        method="POST",
        json_payload={
            "event": "APPROVE",
            "body": f"Approved from Slack reaction :white_check_mark: by <@{reactor_user_id}>.",
        },
        timeout_seconds=10,
    )
    if not bool(approve.get("ok")):
        return {
            "status": "error",
            "error": "github_pr_approve_failed",
            "detail": str(approve.get("error") or ""),
            "pr_url": pr_url,
        }

    merged = False
    merge_error = ""
    branch_deleted = False
    delete_error = ""
    if bool(getattr(settings, "github_slack_auto_merge", False)):
        merge_method = str(getattr(settings, "github_slack_merge_method", "squash") or "squash").strip().lower()
        if merge_method not in {"merge", "squash", "rebase"}:
            merge_method = "squash"
        merge = _github_api_request(
            github_token=github_token,
            path=f"/repos/{owner}/{repo}/pulls/{number}/merge",
            method="PUT",
            json_payload={"merge_method": merge_method},
            timeout_seconds=10,
        )
        merged = bool(merge.get("ok")) and bool((merge.get("payload") or {}).get("merged"))
        if not merged:
            merge_error = str(merge.get("error") or "")

    if merged and bool(getattr(settings, "github_slack_delete_branch", True)):
        safe_head_ref = urlparse.quote(head_ref, safe="") if head_ref else ""
        if safe_head_ref and head_ref != base_ref:
            delete_ref = _github_api_request(
                github_token=github_token,
                path=f"/repos/{owner}/{repo}/git/refs/heads/{safe_head_ref}",
                method="DELETE",
                timeout_seconds=10,
            )
            branch_deleted = bool(delete_ref.get("ok"))
            if not branch_deleted:
                delete_error = str(delete_ref.get("error") or "")

    ack_text = f"✅ PR approved via Slack reaction by <@{reactor_user_id}>: {pr_url}"
    if merged:
        ack_text += " | merged"
        if branch_deleted:
            ack_text += " | branch deleted"
    elif merge_error:
        ack_text += f" | merge_failed={merge_error}"
    if delete_error:
        ack_text += f" | branch_delete_failed={delete_error}"

    _slack_api_request(
        bot_token=slack_bot_token,
        api_method="chat.postMessage",
        form_params={
            "channel": channel_id,
            "thread_ts": message_ts,
            "text": ack_text,
        },
        timeout_seconds=8,
    )
    return {
        "status": "processed",
        "pr_url": pr_url,
        "approved": True,
        "merged": merged,
        "branch_deleted": branch_deleted,
        "merge_error": merge_error,
        "delete_error": delete_error,
        "reactor_user_id": reactor_user_id,
    }


def _build_inbound_payload_from_resend(event_data: Dict[str, Any], fetched_email: Dict[str, Any]) -> Dict[str, Any]:
    from_value = _normalize_sender_value(fetched_email.get("from"))
    if not from_value:
        from_value = _normalize_sender_value(event_data.get("from"))

    to_value = fetched_email.get("to")
    if not to_value:
        to_value = event_data.get("to")

    payload: Dict[str, Any] = {
        "from": from_value,
        "subject": str(fetched_email.get("subject") or event_data.get("subject") or "").strip(),
        "to": _stringify_recipients(to_value),
    }

    text_body = _extract_text_payload(fetched_email, "text", "text_body", "body_text", "plain", "body")
    if not text_body:
        text_body = _extract_text_payload(event_data, "text", "text_body", "body_text", "plain", "body")
    if text_body:
        payload["text"] = text_body

    html_body = _extract_text_payload(fetched_email, "html", "html_body", "body_html")
    if not html_body:
        html_body = _extract_text_payload(event_data, "html", "html_body", "body_html")
    if html_body:
        payload["html"] = html_body

    return payload


def _validate_ticket_payload(
    payload: Dict[str, Any],
    *,
    authenticated_email: str = "",
) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None, int | None]:
    email = _normalize_email(payload.get("email", ""))
    subject = " ".join(str(payload.get("subject", "")).splitlines()).strip()
    message = str(payload.get("message", "")).strip()
    category_key = str(payload.get("category", "") or "").strip().lower().replace(" ", "_")
    bug_surface = str(payload.get("bug_surface", "") or "").strip().lower().replace(" ", "_")
    bug_severity = str(payload.get("bug_severity", "") or "").strip().lower().replace(" ", "_")
    bug_reproducible = str(payload.get("bug_reproducible", "") or "").strip().lower().replace(" ", "_")
    payment_txid = str(payload.get("payment_txid", "") or "").strip()
    payment_chain = str(payload.get("payment_chain", "") or "").strip().lower().replace(" ", "_")
    if payment_chain in PAYMENT_CHAIN_ALIASES:
        payment_chain = PAYMENT_CHAIN_ALIASES[payment_chain]

    locked_email = _normalize_email(authenticated_email)
    if locked_email:
        if email and email != locked_email:
            return (
                None,
                {
                    "error": "email_locked_to_account",
                    "message": "Signed-in users can submit tickets only with their account email.",
                },
                403,
            )
        email = locked_email

    if not _is_valid_email(email):
        return None, {"error": "invalid_payload", "message": "valid email is required"}, 400
    if not subject:
        return None, {"error": "invalid_payload", "message": "subject is required"}, 400
    if not message:
        return None, {"error": "invalid_payload", "message": "message is required"}, 400
    if category_key and category_key not in ALLOWED_TICKET_CATEGORIES:
        return None, {"error": "invalid_payload", "message": "invalid category"}, 400
    if category_key == "bug_report":
        if bug_surface not in ALLOWED_BUG_SURFACES:
            return None, {"error": "invalid_payload", "message": "bug location is required"}, 400
        if bug_severity not in ALLOWED_BUG_SEVERITIES:
            return None, {"error": "invalid_payload", "message": "bug severity is required"}, 400
        if bug_reproducible not in ALLOWED_BUG_REPRODUCIBLE:
            return None, {"error": "invalid_payload", "message": "bug reproducibility is required"}, 400
    else:
        bug_surface = ""
        bug_severity = ""
        bug_reproducible = ""
    if category_key == "payment_issue":
        if not payment_txid:
            return None, {"error": "invalid_payload", "message": "transaction id (TxID) is required"}, 400
        if len(payment_txid) > PAYMENT_TXID_MAX_LENGTH:
            return (
                None,
                {
                    "error": "invalid_payload",
                    "message": f"transaction id must be at most {PAYMENT_TXID_MAX_LENGTH} characters",
                },
                400,
            )
        if not PAYMENT_TXID_PATTERN.fullmatch(payment_txid):
            return None, {"error": "invalid_payload", "message": "transaction id contains invalid characters"}, 400
        if payment_chain not in ALLOWED_PAYMENT_CHAINS:
            return None, {"error": "invalid_payload", "message": "blockchain is required"}, 400
    else:
        payment_txid = ""
        payment_chain = ""

    if len(subject) > TICKET_SUBJECT_MAX_LENGTH:
        return (
            None,
            {
                "error": "invalid_payload",
                "message": f"subject must be at most {TICKET_SUBJECT_MAX_LENGTH} characters",
            },
            400,
        )
    if len(message) > TICKET_BODY_MAX_LENGTH:
        return (
            None,
            {
                "error": "invalid_payload",
                "message": f"message must be at most {TICKET_BODY_MAX_LENGTH} characters",
            },
            400,
        )

    return {
        "email": email,
        "subject": subject,
        "message": message,
        "category_key": category_key,
        "bug_surface": bug_surface,
        "bug_severity": bug_severity,
        "bug_reproducible": bug_reproducible,
        "payment_txid": payment_txid,
        "payment_chain": payment_chain,
    }, None, None


def submit_ticket_payload(
    payload: Dict[str, Any],
    *,
    client_ip: str,
    authenticated_user: Dict[str, Any] | None = None,
    attachments: list[FileStorage] | None = None,
) -> Tuple[Dict[str, Any], int, Dict[str, str]]:
    authenticated_email = ""
    submitter_user_id: int | None = None
    is_authenticated_submitter = False
    if isinstance(authenticated_user, dict):
        authenticated_email = _normalize_email(authenticated_user.get("email", ""))
        try:
            submitter_user_id = int(authenticated_user.get("id") or 0)
        except (TypeError, ValueError):
            submitter_user_id = None
        is_authenticated_submitter = bool(submitter_user_id and authenticated_email)

    cleaned, error_payload, status_code = _validate_ticket_payload(
        payload,
        authenticated_email=authenticated_email,
    )
    if error_payload is not None:
        return error_payload, int(status_code or 400), {}

    assert cleaned is not None
    settings = current_app.config["SETTINGS"]
    ticket_store = current_app.config["SUPPORT_TICKET_STORE"]
    rate_limit = ticket_store.check_and_record_rate_limit(
        client_ip=client_ip,
        customer_email=cleaned["email"],
        ip_per_5m=settings.support_rate_limit_ip_per_5m,
        email_per_5m=settings.support_rate_limit_email_per_5m,
        ip_per_hour=settings.support_rate_limit_ip_per_hour,
        email_per_hour=settings.support_rate_limit_email_per_hour,
    )
    if not rate_limit.get("allowed", False):
        retry_after = int(rate_limit.get("retry_after_seconds", 300))
        return (
            {
                "error": "rate_limited",
                "message": "Too many ticket submissions. Please wait and try again.",
                "reason": rate_limit.get("reason", "rate_limited"),
                "retry_after_seconds": retry_after,
            },
            429,
            {"Retry-After": str(retry_after)},
        )

    raw_uploads = attachments or []
    uploads = [
        item
        for item in raw_uploads
        if isinstance(item, FileStorage) and str(getattr(item, "filename", "") or "").strip()
    ]
    max_files = max(1, min(10, int(getattr(settings, "support_ticket_attachment_max_files", 5) or 5)))
    max_bytes = max(
        1 * 1024 * 1024,
        min(100 * 1024 * 1024, int(getattr(settings, "support_ticket_attachment_max_bytes", 25 * 1024 * 1024) or (25 * 1024 * 1024))),
    )
    use_clamav = bool(getattr(settings, "support_ticket_attachment_scan_clamav", True))
    attachments_dir = str(getattr(settings, "support_ticket_attachments_dir", "") or "").strip()
    if len(uploads) > max_files:
        return (
            {
                "error": "too_many_attachments",
                "message": f"You can attach up to {max_files} files per ticket.",
            },
            400,
            {},
        )

    staged_attachments: list[Dict[str, Any]] = []
    for upload in uploads:
        staged, upload_error, upload_error_status = _scan_and_stage_attachment(
            upload=upload,
            max_bytes=max_bytes,
            use_clamav=use_clamav,
        )
        if upload_error is not None:
            _cleanup_staged_attachments(staged_attachments)
            return upload_error, int(upload_error_status or 400), {}
        assert staged is not None
        staged_attachments.append(staged)

    if cleaned["category_key"]:
        category_key = cleaned["category_key"]
        confidence = 1.0
    else:
        auto_category, confidence = _simple_triage(cleaned["subject"], cleaned["message"])
        category_key = AUTO_CATEGORY_TO_KEY.get(auto_category, "general")

    category = ALLOWED_TICKET_CATEGORIES[category_key]
    ticket = ticket_store.create_ticket(
        customer_email=cleaned["email"],
        subject=cleaned["subject"],
        message=cleaned["message"],
        category=category,
        bug_surface=cleaned["bug_surface"] if category_key == "bug_report" else "",
        bug_severity=cleaned["bug_severity"] if category_key == "bug_report" else "",
        bug_reproducible=cleaned["bug_reproducible"] if category_key == "bug_report" else "",
        payment_txid=cleaned["payment_txid"] if category_key == "payment_issue" else "",
        payment_chain=cleaned["payment_chain"] if category_key == "payment_issue" else "",
        confidence=confidence,
        submitter_user_id=submitter_user_id,
        is_authenticated_submitter=is_authenticated_submitter,
    )
    persisted_attachments: list[Dict[str, Any]] = []
    if staged_attachments:
        try:
            persisted_attachments = _persist_staged_attachments(
                staged=staged_attachments,
                ticket_ref=str(ticket["ticket_ref"]),
                attachments_dir=attachments_dir,
                ticket_store=ticket_store,
            )
            ticket["attachment_count"] = len(persisted_attachments)
        except Exception as exc:
            _cleanup_staged_attachments(staged_attachments)
            _record_operational_alert(
                category="ticket_store",
                severity="error",
                message="Ticket created but attachment persistence failed",
                event_key=f"ticket_attachment_persist_failed:{ticket.get('ticket_ref', '')}",
                context={
                    "ticket_ref": ticket.get("ticket_ref", ""),
                    "error": type(exc).__name__,
                    "attachment_count": len(staged_attachments),
                },
            )
            current_app.logger.exception(
                "ticket_attachment_persist_failed ticket=%s count=%s",
                ticket.get("ticket_ref", ""),
                len(staged_attachments),
            )
    ticket["attachments"] = [
        {
            "id": int(item.get("id") or 0),
            "filename": str(item.get("original_filename") or ""),
            "size_bytes": int(item.get("size_bytes") or 0),
            "mime_type": str(item.get("mime_type") or ""),
        }
        for item in persisted_attachments
    ]

    mailer = current_app.config["SUPPORT_MAILER"]
    email_delivery = mailer.send_ticket_notifications(ticket)
    if not bool(email_delivery.get("configured", False)):
        _record_operational_alert(
            category="support_smtp",
            severity="critical",
            message="Support SMTP is not configured",
            event_key="support_smtp:not_configured",
            context={
                "ticket_ref": ticket["ticket_ref"],
                "email_delivery": email_delivery,
            },
        )
        current_app.logger.error(
            "support_email_not_configured ticket=%s detail=%s",
            ticket["ticket_ref"],
            email_delivery,
        )
    elif (
        str(email_delivery.get("customer_ack", "")).strip().lower() != "sent"
        or str(email_delivery.get("support_summary", "")).strip().lower() != "sent"
    ):
        _record_operational_alert(
            category="support_smtp",
            severity="error",
            message="Support ticket notification delivery failed",
            event_key=f"support_mail_send:{ticket['ticket_ref']}",
            context={
                "ticket_ref": ticket["ticket_ref"],
                "email_delivery": email_delivery,
            },
        )
        current_app.logger.error(
            "support_email_send_failed ticket=%s detail=%s",
            ticket["ticket_ref"],
            email_delivery,
        )
    _notify_support_slack(
        event="new_ticket",
        ticket=ticket,
        sender_email=cleaned["email"],
        message_body=cleaned["message"],
        source="ticket_submission",
    )
    return (
        {
            "ticket_id": ticket["ticket_ref"],
            "created_at_utc": ticket["created_at_utc"],
            "category": ticket["category"],
            "confidence": ticket["confidence"],
            "status": ticket["status"],
            "bug_surface": str(ticket.get("bug_surface") or ""),
            "bug_severity": str(ticket.get("bug_severity") or ""),
            "bug_reproducible": str(ticket.get("bug_reproducible") or ""),
            "payment_txid": str(ticket.get("payment_txid") or ""),
            "payment_chain": str(ticket.get("payment_chain") or ""),
            "attachment_count": int(ticket.get("attachment_count") or len(persisted_attachments)),
            "attachments": list(ticket.get("attachments") or []),
            "email_delivery": email_delivery,
            "message": "Ticket created successfully.",
        },
        201,
        {},
    )


@support_bp.post("/triage")
def triage_ticket():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject", "")).strip()
    message = str(payload.get("message", "")).strip()

    if not subject or not message:
        return jsonify({"error": "invalid_payload", "message": "subject and message are required"}), 400

    category, confidence = _simple_triage(subject, message)
    return jsonify({
        "category": category,
        "confidence": confidence,
        "provider": "local_scaffold",
        "next_step": "manual_review" if confidence < 0.80 else "auto_route",
    })


@support_bp.post("/tickets")
def create_ticket():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict(flat=True)
    if not isinstance(payload, dict):
        payload = {}
    files = request.files.getlist("attachments") if request.files else []
    result_payload, status_code, extra_headers = submit_ticket_payload(
        payload,
        client_ip=_extract_client_ip(),
        authenticated_user=get_current_user(),
        attachments=files,
    )
    response = jsonify(result_payload)
    for header, value in extra_headers.items():
        header_name = str(header or "").strip()
        if not header_name or not _HEADER_NAME_TOKEN_PATTERN.fullmatch(header_name):
            continue
        response.headers[header_name] = sanitize_header_value(str(value))
    return response, status_code


@support_bp.post("/inbound-email")
def ingest_inbound_email_reply():
    authorized, error_payload, error_status = _authorize_inbound_webhook()
    if not authorized:
        return jsonify(error_payload), error_status

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict(flat=True)
    if not isinstance(payload, dict):
        payload = {}

    result_payload, status_code = _ingest_inbound_email_payload(payload)
    return jsonify(result_payload), status_code


@support_bp.post("/inbound-email/resend")
def ingest_resend_inbound_email_reply():
    authorized, error_payload, error_status = _authorize_inbound_webhook()
    if not authorized:
        return jsonify(error_payload), error_status

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_payload", "message": "json payload is required"}), 400

    event_type = str(payload.get("type") or payload.get("event") or payload.get("topic") or "").strip().lower()
    if event_type and event_type != "email.received":
        return jsonify({"status": "ignored", "reason": "unsupported_event_type", "type": event_type}), 202

    event_data = payload.get("data")
    if not isinstance(event_data, dict):
        event_data = payload.get("record")
    if not isinstance(event_data, dict):
        event_data = payload

    email_id = str(
        event_data.get("email_id")
        or event_data.get("emailId")
        or event_data.get("id")
        or event_data.get("message_id")
        or event_data.get("messageId")
        or payload.get("email_id")
        or payload.get("emailId")
        or ""
    ).strip()
    if not email_id and isinstance(event_data.get("email"), dict):
        email_id = str(
            event_data["email"].get("id")
            or event_data["email"].get("email_id")
            or event_data["email"].get("emailId")
            or ""
        ).strip()
    if not email_id:
        return (
            jsonify(
                {
                    "error": "invalid_payload",
                    "message": "email id not found in payload",
                    "payload_keys": sorted(list(payload.keys())),
                    "data_keys": sorted(list(event_data.keys())) if isinstance(event_data, dict) else [],
                }
            ),
            400,
        )

    event_id = str(payload.get("id", "")).strip() or email_id
    current_app.logger.info(
        "resend_inbound_webhook_received event_id=%s email_id=%s type=%s",
        event_id,
        email_id,
        event_type or "email.received",
    )
    store = current_app.config["SUPPORT_TICKET_STORE"]
    if event_id and store.has_webhook_event(provider="resend", event_id=event_id):
        current_app.logger.info(
            "resend_inbound_webhook_duplicate event_id=%s email_id=%s",
            event_id,
            email_id,
        )
        return jsonify({"status": "duplicate", "event_id": event_id}), 200

    settings = current_app.config["SETTINGS"]
    resend_api_key = str(settings.support_resend_api_key or "").strip()
    if not resend_api_key:
        _record_operational_alert(
            category="resend_inbound",
            severity="critical",
            message="Resend API key missing for inbound adapter",
            event_key="resend_inbound:missing_api_key",
            context={"event_id": event_id, "email_id": email_id},
        )
        return jsonify({"error": "resend_api_key_not_configured"}), 503

    fetched_email = None
    fetch_error = None
    # Resend webhook can arrive slightly before the message body is retrievable via API.
    # Retry a few times with short backoff to avoid dropping valid customer replies.
    for idx, delay_seconds in enumerate((0, 1, 2, 4), start=1):
        if delay_seconds:
            time.sleep(delay_seconds)
        fetched_email, fetch_error = _fetch_resend_received_email(
            email_id=email_id,
            api_key=resend_api_key,
            timeout_seconds=settings.support_resend_fetch_timeout_seconds,
        )
        if fetched_email and not fetch_error:
            if idx > 1:
                current_app.logger.info(
                    "resend_inbound_fetch_recovered email_id=%s attempts=%s",
                    email_id,
                    idx,
                )
            break
    if fetch_error or not fetched_email:
        current_app.logger.warning(
            "resend_inbound_fetch_failed event_id=%s email_id=%s error=%s",
            event_id,
            email_id,
            fetch_error or "unknown",
        )
        _record_operational_alert(
            category="resend_inbound",
            severity="error",
            message="Resend inbound fetch failed",
            event_key=f"resend_fetch_failed:{email_id}",
            context={"event_id": event_id, "email_id": email_id, "error": fetch_error or "unknown"},
        )
        return jsonify({"error": "resend_fetch_failed", "message": fetch_error or "failed_to_fetch_email"}), 502

    inbound_payload = _build_inbound_payload_from_resend(event_data, fetched_email)
    result_payload, status_code = _ingest_inbound_email_payload(inbound_payload)
    if int(status_code) == 201:
        current_app.logger.info(
            "resend_inbound_ingested_ok event_id=%s email_id=%s ticket_id=%s author_type=%s",
            event_id,
            email_id,
            result_payload.get("ticket_id", ""),
            result_payload.get("author_type", ""),
        )
    else:
        current_app.logger.warning(
            "resend_inbound_ingest_failed event_id=%s email_id=%s status=%s payload=%s",
            event_id,
            email_id,
            status_code,
            result_payload,
        )
    if int(status_code) == 201 and event_id:
        store.record_webhook_event(provider="resend", event_id=event_id, email_id=email_id)
        result_payload["provider"] = "resend"
        result_payload["email_id"] = email_id
    return jsonify(result_payload), status_code


@support_bp.post("/inbound-email/resend/sync")
def sync_resend_inbound_email_replies():
    authorized, error_payload, error_status = _authorize_inbound_webhook()
    if not authorized:
        return jsonify(error_payload), error_status

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    limit = int(payload.get("limit", 20) or 20)
    limit = max(1, min(limit, 100))

    settings = current_app.config["SETTINGS"]
    resend_api_key = str(settings.support_resend_api_key or "").strip()
    unmapped_alert_threshold = max(
        0,
        int(getattr(settings, "support_resend_sync_unmapped_alert_threshold", 5) or 5),
    )
    unmapped_sustained_runs = max(
        2,
        int(getattr(settings, "support_resend_sync_unmapped_sustained_runs", 3) or 3),
    )
    if not resend_api_key:
        return jsonify({"error": "resend_api_key_not_configured"}), 503

    rows, list_error = _list_resend_received_emails(
        api_key=resend_api_key,
        timeout_seconds=settings.support_resend_fetch_timeout_seconds,
        limit=limit,
    )
    if list_error is not None:
        _record_operational_alert(
            category="resend_inbound",
            severity="warning",
            message="Resend inbound sync failed to list receiving emails",
            event_key="resend_sync_list_failed",
            context={"error": list_error, "limit": limit},
        )
        return jsonify({"error": "resend_sync_list_failed", "message": list_error}), 502

    store = current_app.config["SUPPORT_TICKET_STORE"]
    processed = 0
    duplicates = 0
    unmapped = 0
    failed_hard = 0
    processed_ids: list[str] = []
    unmapped_ticket_ids: list[str] = []
    errors: list[Dict[str, str]] = []

    # Process oldest first so chat chronology remains natural.
    for row in reversed(rows):
        email_id = str(
            row.get("id")
            or row.get("email_id")
            or row.get("emailId")
            or ""
        ).strip()
        if not email_id:
            failed_hard += 1
            continue

        if store.has_webhook_event(provider="resend", event_id=email_id):
            duplicates += 1
            continue

        fetched_email, fetch_error = _fetch_resend_received_email(
            email_id=email_id,
            api_key=resend_api_key,
            timeout_seconds=settings.support_resend_fetch_timeout_seconds,
        )
        if fetch_error or not fetched_email:
            failed_hard += 1
            if len(errors) < 5:
                errors.append({"email_id": email_id, "error": fetch_error or "fetch_failed"})
            continue

        inbound_payload = _build_inbound_payload_from_resend(row, fetched_email)
        result_payload, status_code = _ingest_inbound_email_payload(inbound_payload)
        if int(status_code) == 201:
            store.record_webhook_event(provider="resend", event_id=email_id, email_id=email_id)
            processed += 1
            processed_ids.append(email_id)
            continue

        error_code = str(result_payload.get("error", "ingest_failed")).strip().lower()
        if int(status_code) == 404 and error_code == "ticket_not_found":
            unmapped += 1
            ticket_id = str(result_payload.get("ticket_id", "")).strip()
            if ticket_id and len(unmapped_ticket_ids) < 20:
                unmapped_ticket_ids.append(ticket_id)
            continue

        failed_hard += 1
        if len(errors) < 5:
            errors.append(
                {
                    "email_id": email_id,
                    "status": str(status_code),
                    "error": str(result_payload.get("error", "ingest_failed")),
                }
            )

    run_id = store.record_resend_sync_run(
        checked=len(rows),
        processed=processed,
        duplicates=duplicates,
        unmapped=unmapped,
        failed_hard=failed_hard,
        threshold=unmapped_alert_threshold,
    )
    history_limit = max(2, unmapped_sustained_runs + 1)
    recent_runs = store.list_recent_resend_sync_runs(limit=history_limit)
    current_run = recent_runs[0] if recent_runs else {}
    previous_run = recent_runs[1] if len(recent_runs) > 1 else {}
    current_breach = _run_above_unmapped_threshold(current_run, threshold=unmapped_alert_threshold)
    previous_breach = _run_above_unmapped_threshold(previous_run, threshold=unmapped_alert_threshold)

    if current_breach and not previous_breach:
        _record_operational_alert(
            category="resend_inbound",
            severity="warning",
            message="Resend inbound sync found replies that do not match known tickets",
            event_key="resend_sync_unmapped_threshold",
            context={
                "run_id": run_id,
                "checked": len(rows),
                "processed": processed,
                "duplicates": duplicates,
                "unmapped": unmapped,
                "threshold": unmapped_alert_threshold,
                "sample_ticket_ids": unmapped_ticket_ids[:5],
            },
        )

    sustained_breach = _recent_runs_have_sustained_breach(
        recent_runs,
        threshold=unmapped_alert_threshold,
        consecutive_runs=unmapped_sustained_runs,
    )
    previous_sustained_breach = _recent_runs_have_sustained_breach(
        recent_runs[1:],
        threshold=unmapped_alert_threshold,
        consecutive_runs=unmapped_sustained_runs,
    )
    if sustained_breach and not previous_sustained_breach:
        _record_operational_alert(
            category="resend_inbound",
            severity="critical",
            message="Resend inbound sync unmapped replies remain above threshold across consecutive runs",
            event_key="resend_sync_unmapped_sustained",
            context={
                "run_id": run_id,
                "checked": len(rows),
                "processed": processed,
                "duplicates": duplicates,
                "unmapped": unmapped,
                "threshold": unmapped_alert_threshold,
                "sustained_runs": unmapped_sustained_runs,
                "recent_runs": recent_runs[:unmapped_sustained_runs],
            },
        )

    return (
        jsonify(
            {
                "status": "ok",
                "run_id": run_id,
                "checked": len(rows),
                "processed": processed,
                "duplicates": duplicates,
                "unmapped": unmapped,
                "failed": failed_hard,
                "failed_total": failed_hard + unmapped,
                "processed_email_ids": processed_ids[:20],
                "unmapped_ticket_ids": unmapped_ticket_ids[:20],
                "policy": {
                    "unmapped_threshold": unmapped_alert_threshold,
                    "sustained_runs": unmapped_sustained_runs,
                    "current_breach": current_breach,
                    "sustained_breach": sustained_breach,
                },
                "errors": errors,
            }
        ),
        200,
    )


@support_bp.post("/webhook/trustpilot")
def ingest_trustpilot_review_webhook():
    settings = current_app.config["SETTINGS"]
    configured_secret = str(settings.trustpilot_webhook_secret or "").strip()
    if not configured_secret:
        return jsonify({"error": "trustpilot_webhook_not_configured"}), 503

    supplied_secret = _extract_secret_from_request("X-Trustpilot-Webhook-Secret", "X-Trustpilot-Secret")
    if not supplied_secret or not secrets.compare_digest(supplied_secret, configured_secret):
        return jsonify({"error": "unauthorized"}), 401

    if not bool(settings.trustpilot_slack_enabled) or not str(settings.trustpilot_slack_webhook_url or "").strip():
        return jsonify({"error": "trustpilot_slack_not_configured"}), 503

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_payload", "message": "json payload is required"}), 400

    event_id = _build_trustpilot_event_id(payload)
    store = current_app.config.get("SUPPORT_TICKET_STORE")
    if store is not None and store.has_webhook_event(provider="trustpilot", event_id=event_id):
        return jsonify({"status": "duplicate", "event_id": event_id}), 200

    event_type = _extract_nested_value(
        payload,
        ("eventName",),
        ("event",),
        ("event_type",),
        ("eventType",),
        ("type",),
    ) or "review.event"
    stars = _format_trustpilot_stars(payload) or "-"
    reviewer = _extract_nested_value(
        payload,
        ("consumer", "displayName"),
        ("reviewer", "displayName"),
        ("consumer", "name"),
        ("reviewer", "name"),
        ("author", "name"),
        ("name",),
    ) or "Anonymous"
    business_unit = _extract_nested_value(
        payload,
        ("businessUnit", "name"),
        ("business_unit", "name"),
        ("businessUnitName",),
        ("domain",),
    ) or "Hodler Suite"
    title = _extract_nested_value(
        payload,
        ("review", "title"),
        ("title",),
        ("data", "title"),
    )
    body = _extract_nested_value(
        payload,
        ("review", "text"),
        ("text",),
        ("body",),
        ("data", "text"),
    )
    review_url = _extract_nested_value(
        payload,
        ("review", "url"),
        ("url",),
        ("permalink",),
        ("link",),
        ("reviewUrl",),
        ("review_url",),
    )
    created_at = _extract_nested_value(
        payload,
        ("review", "createdAt"),
        ("createdAt",),
        ("created_at",),
        ("date",),
    )

    lines = [
        "⭐ *Trustpilot Review Event*",
        f"*Event:* {event_type}",
        f"*Business Unit:* {business_unit}",
        f"*Stars:* {stars}",
        f"*Reviewer:* {reviewer}",
    ]
    if title:
        lines.append(f"*Title:* {_short_text(title, limit=160)}")
    if body:
        lines.append(f"*Body:* {_short_text(body, limit=260)}")
    if created_at:
        lines.append(f"*Created:* {created_at}")
    if review_url:
        lines.append(f"*Review:* {review_url}")
    lines.append(f"*Event ID:* `{event_id}`")

    result = _post_slack_webhook(
        webhook_url=settings.trustpilot_slack_webhook_url,
        timeout_seconds=settings.trustpilot_slack_timeout_seconds,
        payload={"text": "\n".join(lines)},
    )
    if not bool(result.get("sent")):
        _record_operational_alert(
            category="trustpilot_reviews",
            severity="warning",
            message="Trustpilot review webhook could not be relayed to Slack",
            event_key=f"trustpilot_slack_failed:{event_id}",
            context={
                "event_id": event_id,
                "event_type": event_type,
                "error": str(result.get("error", "unknown_error")),
                "detail": str(result.get("detail", "")),
            },
        )
        return jsonify({"error": "slack_delivery_failed", "detail": result}), 502

    if store is not None:
        store.record_webhook_event(provider="trustpilot", event_id=event_id, email_id="")

    return jsonify({"status": "accepted", "event_id": event_id, "event_type": event_type}), 200


@support_bp.post("/slack/events")
def slack_events_webhook():
    settings = current_app.config["SETTINGS"]
    signing_secret = str(getattr(settings, "slack_events_signing_secret", "") or "").strip()
    if not signing_secret:
        return jsonify({"error": "slack_events_not_configured"}), 503

    raw_body = request.get_data(cache=True, as_text=False) or b""
    if not _verify_slack_events_signature(signing_secret=signing_secret, raw_body=raw_body):
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_payload"}), 400

    if str(payload.get("type", "")).strip() == "url_verification":
        return jsonify({"challenge": str(payload.get("challenge", "")).strip()}), 200

    event_id = str(payload.get("event_id", "")).strip()
    if event_id and _is_duplicate_slack_event(event_id):
        return jsonify({"ok": True, "status": "duplicate"}), 200

    if str(payload.get("type", "")).strip() != "event_callback":
        return jsonify({"ok": True, "status": "ignored"}), 200

    event = payload.get("event")
    if not isinstance(event, dict):
        return jsonify({"ok": True, "status": "ignored"}), 200

    if str(event.get("type", "")).strip() != "reaction_added":
        return jsonify({"ok": True, "status": "ignored"}), 200

    result = _process_github_pr_approval_reaction(event=event)
    if str(result.get("status", "")).strip().lower() == "error":
        _record_operational_alert(
            category="support_notify",
            severity="warning",
            message="Slack reaction PR automation failed",
            event_key=f"slack_reaction_pr_failed:{event_id or 'no_event_id'}",
            context={
                "event_id": event_id,
                "result": result,
            },
        )
    return jsonify({"ok": True, "result": result}), 200
