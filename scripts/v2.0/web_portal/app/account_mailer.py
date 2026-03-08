"""SMTP notifications for account onboarding and verification."""

from __future__ import annotations

from email.message import EmailMessage
import html
import smtplib
from typing import Any, Dict

from .config import Settings


class AccountMailer:
    def __init__(self, settings: Settings) -> None:
        self.host = settings.support_smtp_host
        self.port = int(settings.support_smtp_port)
        self.username = settings.support_smtp_username
        self.password = settings.support_smtp_password
        self.use_tls = bool(settings.support_smtp_use_tls)
        self.use_ssl = bool(settings.support_smtp_use_ssl)
        self.from_address = settings.account_email_from
        self.subject_prefix = settings.account_email_subject_prefix.strip() or "[Hodler Suite]"
        self.brand_logo_url = str(settings.email_brand_logo_url or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.host and self.from_address)

    def _authenticate_if_needed(self, smtp: smtplib.SMTP) -> None:
        if self.username:
            smtp.login(self.username, self.password)

    def _wrap_html(self, content_html: str) -> str:
        body = str(content_html or "").strip()
        if not body:
            return ""
        if not self.brand_logo_url:
            return body
        logo_url = html.escape(self.brand_logo_url, quote=True)
        return (
            "<div style=\"font-family:Arial,sans-serif;line-height:1.45;color:#0f172a;\">"
            f"<p style=\"margin:0 0 14px;\"><img src=\"{logo_url}\" alt=\"Hodler Suite\" width=\"72\" "
            "style=\"display:block;border:0;outline:none;text-decoration:none;\"></p>"
            f"{body}"
            "</div>"
        )

    def _attach_html(self, message: EmailMessage, content_html: str) -> None:
        wrapped = self._wrap_html(content_html)
        if wrapped:
            message.add_alternative(wrapped, subtype="html")

    def _send(self, message: EmailMessage) -> None:
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=15) as smtp:
                self._authenticate_if_needed(smtp)
                smtp.send_message(message)
            return

        with smtplib.SMTP(self.host, self.port, timeout=15) as smtp:
            smtp.ehlo()
            if self.use_tls:
                smtp.starttls()
                smtp.ehlo()
            self._authenticate_if_needed(smtp)
            smtp.send_message(message)

    def send_signup_code(self, *, email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} Email confirmation code"
        body = (
            "Hodler Suite email verification\n\n"
            f"Your confirmation code is: {code}\n\n"
            f"This code expires in {int(expires_minutes)} minutes.\n"
            "Do not share this code with anyone."
        )
        html = (
            "<p><strong>Hodler Suite email verification</strong></p>"
            f"<p>Your confirmation code is: <strong>{code}</strong></p>"
            f"<p>This code expires in <strong>{int(expires_minutes)} minutes</strong>.</p>"
            "<p>Do not share this code with anyone.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_welcome_email(self, *, email: str) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} Welcome to Hodler Suite"
        body = (
            "Welcome to Hodler Suite.\n\n"
            "Your account is now active and verified. We are glad to have you onboard.\n"
            "You can now access your dashboard, run assessments, and manage your account securely.\n\n"
            "Warm regards,\n"
            "Hodler Suite Team"
        )
        html = (
            "<p>Welcome to <strong>Hodler Suite</strong>.</p>"
            "<p>Your account is now active and verified. We are glad to have you onboard.</p>"
            "<p>You can now access your dashboard, run assessments, and manage your account securely.</p>"
            "<p>Warm regards,<br>Hodler Suite Team</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_password_reset_email(self, *, email: str, reset_url: str, expires_minutes: int) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} Password reset request"
        body = (
            "Hodler Suite account security\n\n"
            "We received a request to reset your password.\n"
            f"Open this link to set a new password (valid for {int(expires_minutes)} minutes):\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )
        html = (
            "<p><strong>Hodler Suite account security</strong></p>"
            "<p>We received a request to reset your password.</p>"
            f"<p>Open this link to set a new password (valid for <strong>{int(expires_minutes)} minutes</strong>):<br>"
            f"<a href=\"{reset_url}\">{reset_url}</a></p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_password_changed_notice(self, *, email: str) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} Password changed"
        body = (
            "Hodler Suite account security\n\n"
            "Your account password has been changed successfully.\n"
            "If you did not perform this action, contact support immediately."
        )
        html = (
            "<p><strong>Hodler Suite account security</strong></p>"
            "<p>Your account password has been changed successfully.</p>"
            "<p>If you did not perform this action, contact support immediately.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_twofa_reset_code(self, *, email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} 2FA reset code"
        body = (
            "Hodler Suite account security\n\n"
            f"Your 2FA reset code is: {code}\n\n"
            f"This code expires in {int(expires_minutes)} minutes.\n"
            "Do not share this code with anyone."
        )
        html = (
            "<p><strong>Hodler Suite account security</strong></p>"
            f"<p>Your 2FA reset code is: <strong>{code}</strong></p>"
            f"<p>This code expires in <strong>{int(expires_minutes)} minutes</strong>.</p>"
            "<p>Do not share this code with anyone.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_twofa_reset_notice(self, *, email: str) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} 2FA reset completed"
        body = (
            "Hodler Suite account security\n\n"
            "Two-factor authentication has been reset for your account.\n"
            "Re-enable 2FA from Account Settings as soon as possible."
        )
        html = (
            "<p><strong>Hodler Suite account security</strong></p>"
            "<p>Two-factor authentication has been reset for your account.</p>"
            "<p>Re-enable 2FA from Account Settings as soon as possible.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_email_change_code(self, *, email: str, code: str, expires_minutes: int) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} Email change verification code"
        body = (
            "Hodler Suite account security\n\n"
            f"Your email change verification code is: {code}\n\n"
            f"This code expires in {int(expires_minutes)} minutes.\n"
            "Do not share this code with anyone."
        )
        html = (
            "<p><strong>Hodler Suite account security</strong></p>"
            f"<p>Your email change verification code is: <strong>{code}</strong></p>"
            f"<p>This code expires in <strong>{int(expires_minutes)} minutes</strong>.</p>"
            "<p>Do not share this code with anyone.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_email_changed_notice(self, *, old_email: str, new_email: str) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        subject = f"{self.subject_prefix} Email address changed"
        body = (
            "Hodler Suite account security\n\n"
            f"Your account email has been changed from {old_email} to {new_email}.\n"
            "If you did not perform this action, contact support immediately."
        )
        html = (
            "<p><strong>Hodler Suite account security</strong></p>"
            f"<p>Your account email has been changed from <strong>{old_email}</strong> to <strong>{new_email}</strong>.</p>"
            "<p>If you did not perform this action, contact support immediately.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = ", ".join([old_email, new_email])
        msg["Subject"] = subject
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_ticket_status_notice(self, *, email: str, ticket_ref: str, status: str) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"in_progress", "resolved"}:
            return {"sent": False, "error": "unsupported_status"}

        if normalized_status == "in_progress":
            status_title = "In Progress"
            detail = (
                f"Your ticket {ticket_ref} is now in progress.\n"
                "A support agent is currently handling your request."
            )
        else:
            status_title = "Resolved"
            detail = (
                f"Your ticket {ticket_ref} has been marked as resolved.\n"
                "If you still need help, reply to the latest support email and include your ticket ID."
            )

        subject = f"{self.subject_prefix} Ticket {ticket_ref} status update: {status_title}"
        body = (
            "Hodler Suite ticket update\n\n"
            f"{detail}\n\n"
            "Best regards,\n"
            "Hodler Suite Support"
        )
        html = (
            "<p><strong>Hodler Suite ticket update</strong></p>"
            f"<p>{detail.replace(chr(10), '<br>')}</p>"
            "<p>Best regards,<br>Hodler Suite Support</p>"
        )

        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = email
        msg["Subject"] = subject
        msg.set_content(body)
        msg.add_alternative(html, subtype="html")

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}
