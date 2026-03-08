"""SMTP notifications for help-desk ticket lifecycle events."""

from __future__ import annotations

from email.message import EmailMessage
import html
import smtplib
from typing import Any, Dict

from .config import Settings


class SupportMailer:
    def __init__(self, settings: Settings) -> None:
        self.host = settings.support_smtp_host
        self.port = int(settings.support_smtp_port)
        self.username = settings.support_smtp_username
        self.password = settings.support_smtp_password
        self.use_tls = bool(settings.support_smtp_use_tls)
        self.use_ssl = bool(settings.support_smtp_use_ssl)
        self.from_address = settings.support_email_from
        self.support_address = settings.support_email_notify_to
        self.inbound_reply_to = str(settings.support_inbound_reply_to or settings.support_email_notify_to).strip()
        self.inbound_routing_active = bool(settings.support_inbound_routing_active)
        self.subject_prefix = settings.support_email_subject_prefix.strip() or "[Hodler Suite]"
        self.brand_logo_url = str(settings.email_brand_logo_url or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.host and self.from_address and self.support_address)

    def _support_sender_address(self) -> str:
        primary = str(self.support_address or "").split(",")[0].strip()
        return primary or self.from_address

    def _reply_to_target(self) -> str:
        if self.inbound_routing_active and self.inbound_reply_to:
            return self.inbound_reply_to
        return self._support_sender_address()

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

    def send_ticket_notifications(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "customer_ack": "skipped",
                "support_summary": "skipped",
                "error": "smtp_not_configured",
            }

        result = {
            "configured": True,
            "customer_ack": "sent",
            "support_summary": "sent",
        }

        try:
            customer_message = self._build_customer_ack(ticket)
            self._send(customer_message)
        except Exception as exc:  # pragma: no cover - network dependency
            result["customer_ack"] = "failed"
            result["customer_error"] = str(exc)

        try:
            summary_message = self._build_support_summary(ticket)
            self._send(summary_message)
        except Exception as exc:  # pragma: no cover - network dependency
            result["support_summary"] = "failed"
            result["support_error"] = str(exc)

        return result

    def send_customer_followup_notification(self, *, ticket: Dict[str, Any], message_body: str) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        body = str(message_body or "").strip()
        if not body:
            return {"sent": False, "error": "empty_message"}
        if len(body) > 8000:
            body = body[:8000]

        subject = f"{self.subject_prefix} Customer reply {ticket['ticket_ref']}"
        plain = (
            "Hello Support Team,\n\n"
            f"The customer replied on ticket {ticket['ticket_ref']}.\n\n"
            f"Customer: {ticket['customer_email']}\n"
            f"Subject: {ticket['subject']}\n\n"
            "Message:\n"
            f"{body}\n\n"
            "Reply to this email to answer the customer.\n"
        )
        escaped_body = html.escape(body).replace("\n", "<br>")
        html_body = (
            "<p>Hello Support Team,</p>"
            f"<p>The customer replied on ticket <strong>{ticket['ticket_ref']}</strong>.</p>"
            f"<p><strong>Customer:</strong> {html.escape(str(ticket['customer_email']))}<br>"
            f"<strong>Subject:</strong> {html.escape(str(ticket['subject']))}</p>"
            f"<p><strong>Message:</strong><br>{escaped_body}</p>"
            "<p>Reply to this email to answer the customer.</p>"
        )

        msg = EmailMessage()
        msg["From"] = self._support_sender_address()
        msg["To"] = self.support_address
        msg["Reply-To"] = self._reply_to_target()
        msg["Subject"] = subject
        msg.set_content(plain)
        self._attach_html(msg, html_body)
        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def send_agent_reply(
        self,
        *,
        ticket: Dict[str, Any],
        reply_body: str,
        agent_email: str,
    ) -> Dict[str, Any]:
        if not self.configured:
            return {"sent": False, "error": "smtp_not_configured"}

        message_body = str(reply_body or "").strip()
        if not message_body:
            return {"sent": False, "error": "empty_message"}
        if len(message_body) > 8000:
            message_body = message_body[:8000]

        subject = f"{self.subject_prefix} Re: {ticket['ticket_ref']}"
        escaped_reply = html.escape(message_body).replace("\n", "<br>")
        plain = (
            f"Hello,\n\n{message_body}\n\n"
            f"Ticket ID: {ticket['ticket_ref']}\n"
            f"Handled by: {agent_email}\n\n"
            "Best regards,\n"
            "Hodler Suite Support"
        )
        html_body = (
            "<p>Hello,</p>"
            f"<p>{escaped_reply}</p>"
            f"<p><strong>Ticket ID:</strong> {ticket['ticket_ref']}<br>"
            f"<strong>Handled by:</strong> {agent_email}</p>"
            "<p>Best regards,<br>Hodler Suite Support</p>"
        )

        msg = EmailMessage()
        msg["From"] = self._support_sender_address()
        msg["To"] = ticket["customer_email"]
        msg["Reply-To"] = self._reply_to_target()
        msg["Subject"] = subject
        msg.set_content(plain)
        self._attach_html(msg, html_body)

        try:
            self._send(msg)
            return {"sent": True}
        except Exception as exc:  # pragma: no cover - network dependency
            return {"sent": False, "error": str(exc)}

    def _build_customer_ack(self, ticket: Dict[str, Any]) -> EmailMessage:
        subject = f"{self.subject_prefix} Ticket {ticket['ticket_ref']} received"
        body = (
            "Dear Customer,\n\n"
            "Thanks for contacting with Hodler Suite Support.\n\n"
            f"We have created ticket {ticket['ticket_ref']} for your request and our team will review it as soon as possible.\n\n"
            "If you have further details to share regarding this case, please reply directly to this email "
            "and keep the ticket ID in the subject line.\n\n"
            "Best regards,\n"
            "Hodler Suite Support"
        )
        html_body = (
            "<p>Dear Customer,</p>"
            "<p>Thanks for contacting with Hodler Suite Support.</p>"
            f"<p>We have created ticket {ticket['ticket_ref']} for your request and our team will review it as soon as possible.</p>"
            "<p>If you have further details to share regarding this case, please reply directly to this email "
            "and keep the ticket ID in the subject line.</p>"
            "<p>Best regards,<br>Hodler Suite Support</p>"
        )

        msg = EmailMessage()
        msg["From"] = self._support_sender_address()
        msg["To"] = ticket["customer_email"]
        msg["Reply-To"] = self._reply_to_target()
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html_body)
        return msg

    def _build_support_summary(self, ticket: Dict[str, Any]) -> EmailMessage:
        subject = f"{self.subject_prefix} New ticket {ticket['ticket_ref']}"
        body = (
            "Hello Support Team,\n\n"
            f"You have received ticket {ticket['ticket_ref']} from {ticket['customer_email']}.\n"
            "Please take care of the request and review it as soon as possible.\n\n"
            f"Category: {ticket['category']}\n"
            f"Subject: {ticket['subject']}\n"
            "Message:\n"
            f"{ticket['message']}\n\n"
            "Reply to this email to answer the customer.\n\n"
            "Best regards,\n"
            "Hodler Suite Support Ticket System\n"
        )
        escaped_message = html.escape(str(ticket["message"])).replace("\n", "<br>")
        html_body = (
            "<p>Hello Support Team,</p>"
            f"<p>You have received ticket <strong>{ticket['ticket_ref']}</strong> from "
            f"{html.escape(str(ticket['customer_email']))}.</p>"
            "<p>Please take care of the request and review it as soon as possible.</p>"
            f"<p><strong>Category:</strong> {html.escape(str(ticket['category']))}<br>"
            f"<strong>Subject:</strong> {html.escape(str(ticket['subject']))}</p>"
            f"<p><strong>Message:</strong><br>{escaped_message}</p>"
            "<p>Reply to this email to answer the customer.</p>"
            "<p>Best regards,<br>Hodler Suite Support Ticket System</p>"
        )

        msg = EmailMessage()
        msg["From"] = self._support_sender_address()
        msg["To"] = self.support_address
        msg["Reply-To"] = self._reply_to_target()
        msg["Subject"] = subject
        msg.set_content(body)
        self._attach_html(msg, html_body)
        return msg
