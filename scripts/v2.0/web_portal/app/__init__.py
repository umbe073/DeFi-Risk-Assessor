"""Flask application factory for the web portal scaffold."""

from datetime import datetime, timedelta, timezone
import time
from urllib.parse import urlsplit
import uuid

from flask import Flask, redirect, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from .account_mailer import AccountMailer
from .auth import get_csrf_token, get_current_user, load_current_user
from .billing_store import BillingStore
from .config import load_settings
from .routes.auth import auth_bp
from .routes.billing import billing_bp
from .routes.health import health_bp
from .routes.pages import pages_bp
from .routes.risk import risk_bp
from .routes.support import support_bp
from .risk_job_store import RiskJobStore
from .security import apply_security_headers
from .security_url import join_trusted_base_url
from .special_accounts import SPECIAL_ENTERPRISE_EMAILS
from .status_store import StatusStore
from .slack_notifier import SupportSlackNotifier
from .support_mailer import SupportMailer
from .ticket_store import TicketStore
from .user_store import UserStore


LEGACY_SESSION_COOKIE_NAMES = {"session"}


def _delete_cookie_variants(
    response,
    *,
    cookie_name: str,
    cookie_path: str,
    configured_domain: str = "",
) -> None:
    request_host = str(request.host or "").split(":", 1)[0].strip().lower()
    domains: list[str | None] = [None]
    if request_host:
        domains.append(request_host)
    normalized_domain = str(configured_domain or "").strip()
    if normalized_domain:
        domains.append(normalized_domain)
        domains.append(normalized_domain.lstrip("."))

    seen: set[str] = set()
    for domain in domains:
        key = str(domain or "<none>")
        if key in seen:
            continue
        seen.add(key)
        response.delete_cookie(cookie_name, path=cookie_path, domain=domain)


def create_app() -> Flask:
    app = Flask(__name__)
    # Trust first reverse-proxy hop for scheme/host when running behind Nginx.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)  # type: ignore[assignment]
    settings = load_settings()
    app.config["SETTINGS"] = settings
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["SESSION_COOKIE_NAME"] = str(getattr(settings, "session_cookie_name", "") or "").strip() or "hs_portal_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = settings.force_https
    session_cookie_domain = str(getattr(settings, "session_cookie_domain", "") or "").strip()
    if session_cookie_domain:
        app.config["SESSION_COOKIE_DOMAIN"] = session_cookie_domain
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=settings.session_idle_minutes)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    app.config["APP_STARTED_AT_UTC"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Keep template edits visible during local scaffold development.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

    user_store = UserStore(settings.auth_db_path)
    app.config["USER_STORE"] = user_store
    app.config["SUPPORT_TICKET_STORE"] = TicketStore(settings.support_ticket_db_path)
    app.config["BILLING_STORE"] = BillingStore(settings.billing_db_path)
    app.config["STATUS_STORE"] = StatusStore(settings.status_db_path)
    app.config["RISK_JOB_STORE"] = RiskJobStore(settings.risk_job_db_path)
    app.config["SUPPORT_MAILER"] = SupportMailer(settings)
    app.config["ACCOUNT_MAILER"] = AccountMailer(settings)
    app.config["SUPPORT_SLACK_NOTIFIER"] = SupportSlackNotifier(settings)
    user_store.ensure_master_account(
        email=settings.master_account_email,
        password_hash=generate_password_hash(settings.master_account_password),
    )
    for special_email in sorted(SPECIAL_ENTERPRISE_EMAILS):
        special_user = user_store.get_user_by_email(special_email)
        if not special_user:
            continue
        user_store.set_active(int(special_user["id"]), True)
        app.config["BILLING_STORE"].assign_unlimited_enterprise(
            user_id=int(special_user["id"]),
            user_email=str(special_user["email"]).strip().lower(),
            source="special_account_bootstrap",
        )

    if settings.user_telemetry_purge_on_startup:
        try:
            telemetry_purge = user_store.purge_user_telemetry(
                user_operation_retention_days=settings.user_operation_retention_days,
                user_device_retention_days=settings.user_device_retention_days,
                user_login_context_retention_days=settings.user_login_context_retention_days,
                dry_run=False,
            )
            deleted_rows = telemetry_purge.get("deleted_rows", {})
            app.logger.info(
                "user_telemetry_retention_applied op=%s devices=%s login_contexts=%s total=%s",
                int((deleted_rows or {}).get("user_operation_logs", 0) or 0),
                int((deleted_rows or {}).get("user_devices", 0) or 0),
                int((deleted_rows or {}).get("user_login_contexts", 0) or 0),
                int((deleted_rows or {}).get("total", 0) or 0),
            )
        except Exception:
            app.logger.exception("user_telemetry_retention_apply_failed")

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(support_bp)

    @app.before_request
    def _load_user():
        load_current_user()

    @app.before_request
    def _enforce_host_split():
        settings = app.config["SETTINGS"]
        app_base_url = str(getattr(settings, "web_portal_app_base_url", "") or "").strip()
        marketing_base_url = str(getattr(settings, "web_portal_marketing_base_url", "") or "").strip()
        if not app_base_url or not marketing_base_url:
            return None

        app_host = str(urlsplit(app_base_url).hostname or "").strip().lower()
        marketing_host = str(urlsplit(marketing_base_url).hostname or "").strip().lower()
        if not app_host or not marketing_host or app_host == marketing_host:
            return None

        request_host = str(request.host or "").split(":", 1)[0].strip().lower()
        if request_host not in {app_host, marketing_host}:
            return None

        path = str(request.path or "")
        if request.method == "OPTIONS":
            return None
        # Preserve semantics for state-changing routes (logout/forms/apis).
        # Cross-host routing is enforced on safe browser navigations.
        if request.method not in {"GET", "HEAD"}:
            return None
        if path.startswith("/api/") or path.startswith("/healthz") or path.startswith("/static/"):
            return None

        query = request.query_string.decode("utf-8", errors="ignore")
        suffix = f"{path}?{query}" if query else path
        user = get_current_user()
        if user and request_host == marketing_host:
            return redirect(join_trusted_base_url(app_base_url, suffix))
        if not user and request_host == app_host:
            return redirect(join_trusted_base_url(marketing_base_url, suffix))
        return None

    @app.before_request
    def _enforce_human_check():
        settings = app.config["SETTINGS"]
        if not settings.turnstile_enforce:
            return None
        now_epoch = int(time.time())
        human_verified = bool(session.get("human_verified"))
        try:
            verified_at_epoch = int(session.get("human_verified_at_epoch") or 0)
        except (TypeError, ValueError):
            verified_at_epoch = 0
        max_human_ttl_seconds = 6 * 60 * 60
        if human_verified:
            if verified_at_epoch > 0 and (now_epoch - verified_at_epoch) <= max_human_ttl_seconds:
                return None
            session.pop("human_verified", None)
            session.pop("human_verified_at_epoch", None)

        endpoint = str(request.endpoint or "")
        path = str(request.path or "")
        if request.method == "OPTIONS":
            return None
        if endpoint in {"pages.human_check", "health.healthz", "static"}:
            return None
        if endpoint in {
            "auth.two_factor_challenge",
            "auth.two_factor_recovery_send_code",
            "auth.two_factor_recovery_verify",
        }:
            # Keep 2FA login/recovery flows stable and avoid redirect loops on submit.
            return None
        if path.startswith("/api/") or path.startswith("/healthz") or path.startswith("/static/"):
            return None

        next_target = request.full_path if request.query_string else request.path
        session["human_check_next"] = next_target
        return redirect(url_for("pages.human_check", next=next_target))

    @app.context_processor
    def _inject_auth_context():
        user = get_current_user()
        support_unread_total = 0
        support_operational_alert_total = 0
        if user and str(user.get("role", "")).lower() in {"master", "admin"}:
            try:
                support_unread_total = int(app.config["SUPPORT_TICKET_STORE"].count_total_unread_customer_messages())
            except Exception:
                support_unread_total = 0
            try:
                support_operational_alert_total = int(app.config["SUPPORT_TICKET_STORE"].count_open_operational_alerts())
            except Exception:
                support_operational_alert_total = 0
        return {
            "current_user": user,
            "csrf_token": get_csrf_token,
            "support_unread_total": support_unread_total,
            "support_operational_alert_total": support_operational_alert_total,
        }

    @app.after_request
    def _apply_headers(response):
        response = apply_security_headers(response, settings)
        # Prevent stale anonymous HTML from being reused after login/logout.
        content_type = (response.mimetype or "").lower()
        if content_type == "text/html":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            existing_vary = response.headers.get("Vary", "")
            vary_values = {value.strip().lower() for value in existing_vary.split(",") if value.strip()}
            if "cookie" not in vary_values:
                response.headers["Vary"] = f"{existing_vary}, Cookie".strip(", ")
        device_uuid = str(session.get("device_uuid", "")).strip()
        if device_uuid:
            try:
                str(uuid.UUID(device_uuid))
                if str(request.cookies.get("hs_device_uuid", "")).strip() != device_uuid:
                    response.set_cookie(
                        "hs_device_uuid",
                        device_uuid,
                        max_age=60 * 60 * 24 * 365 * 2,
                        secure=settings.force_https,
                        httponly=True,
                        samesite="Lax",
                        path="/",
                    )
            except ValueError:
                pass

        session_cookie_name = str(app.config.get("SESSION_COOKIE_NAME", "session") or "session").strip() or "session"
        session_cookie_path = str(app.config.get("SESSION_COOKIE_PATH", "/") or "/").strip() or "/"
        session_cookie_domain = str(app.config.get("SESSION_COOKIE_DOMAIN", "") or "").strip()
        for legacy_cookie_name in sorted(LEGACY_SESSION_COOKIE_NAMES):
            if legacy_cookie_name == session_cookie_name:
                continue
            if legacy_cookie_name not in request.cookies:
                continue
            _delete_cookie_variants(
                response,
                cookie_name=legacy_cookie_name,
                cookie_path=session_cookie_path,
                configured_domain=session_cookie_domain,
            )
        return response

    return app
