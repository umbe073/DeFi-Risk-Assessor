"""Configuration loader for the web portal scaffold."""

from dataclasses import dataclass
import json
import os
from typing import Any, List
from urllib.parse import urlparse


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_list(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_plan_catalog(value: str) -> dict[str, float]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(decoded, dict):
        return {}

    catalog: dict[str, float] = {}
    for raw_plan, raw_amount in decoded.items():
        plan = str(raw_plan or "").strip()
        if not plan:
            continue
        try:
            amount = float(raw_amount)
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        catalog[plan] = round(amount, 2)
    return catalog


def _to_pay_currency_options(value: str) -> list[dict[str, str]]:
    default_options = [
        {"code": "usdttrc20", "label": "USDT (TRC-20)"},
        {"code": "usdc", "label": "USDC (ERC-20)"},
    ]
    text = str(value or "").strip()
    if not text:
        return default_options
    try:
        decoded: Any = json.loads(text)
    except json.JSONDecodeError:
        return default_options

    options: list[dict[str, str]] = []
    if isinstance(decoded, list):
        for item in decoded:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code", "")).strip().lower()
            label = str(item.get("label", "")).strip()
            if not code:
                continue
            options.append({"code": code, "label": label or code.upper()})
    elif isinstance(decoded, dict):
        for raw_code, raw_label in decoded.items():
            code = str(raw_code or "").strip().lower()
            if not code:
                continue
            label = str(raw_label or "").strip()
            options.append({"code": code, "label": label or code.upper()})

    return options or default_options


def _normalize_base_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _default_ip_intel_lookup_url(api_key: str) -> str:
    if not str(api_key or "").strip():
        return ""
    return "https://api.ip2location.io/?key={api_key}&ip={ip}&format=json"


def _derive_marketing_base_url_from_app(app_base_url: str) -> str:
    parsed = urlparse(str(app_base_url or "").strip())
    host = str(parsed.hostname or "").strip().lower()
    scheme = str(parsed.scheme or "").strip().lower()
    if not host or not scheme:
        return ""
    if not host.startswith("app.") or len(host) <= 4:
        return ""
    marketing_host = host[4:]
    if parsed.port:
        marketing_host = f"{marketing_host}:{parsed.port}"
    return f"{scheme}://{marketing_host}"


def _derive_cookie_domain(app_base_url: str, marketing_base_url: str) -> str:
    app_host = str(urlparse(str(app_base_url or "").strip()).hostname or "").strip().lower()
    marketing_host = str(urlparse(str(marketing_base_url or "").strip()).hostname or "").strip().lower()
    if not app_host or not marketing_host:
        return ""

    cookie_host = ""
    if app_host == marketing_host:
        cookie_host = app_host
    elif app_host.endswith(f".{marketing_host}"):
        cookie_host = marketing_host
    elif marketing_host.endswith(f".{app_host}"):
        cookie_host = app_host

    if not cookie_host:
        return ""
    if cookie_host == "localhost" or cookie_host.replace(".", "").isdigit():
        return ""
    return f".{cookie_host}"


def _normalize_cookie_domain(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        raw = str(urlparse(raw).hostname or "").strip().lower()
    if ":" in raw:
        raw = raw.split(":", 1)[0].strip().lower()
    raw = raw.lstrip(".")
    if not raw:
        return ""
    if raw == "localhost" or raw.replace(".", "").isdigit():
        return ""
    return f".{raw}"


def _cookie_domain_matches_host(cookie_domain: str, host: str) -> bool:
    normalized_domain = str(cookie_domain or "").strip().lower().lstrip(".")
    normalized_host = str(host or "").strip().lower()
    if not normalized_domain or not normalized_host:
        return False
    return normalized_host == normalized_domain or normalized_host.endswith(f".{normalized_domain}")


def _cookie_domain_covers_hosts(cookie_domain: str, *hosts: str) -> bool:
    normalized_hosts = [str(host or "").strip().lower() for host in hosts if str(host or "").strip()]
    if not normalized_hosts:
        return False
    return all(_cookie_domain_matches_host(cookie_domain, host) for host in normalized_hosts)


@dataclass(frozen=True)
class Settings:
    secret_key: str
    force_https: bool
    allowed_origins: List[str]
    auth_db_path: str
    auth_2fa_issuer: str
    master_account_email: str
    master_account_password: str
    session_idle_minutes: int
    sensitive_ops_require_2fa: bool
    auth_anomaly_prompt_enabled: bool
    ip_intel_lookup_url: str
    ip_intel_api_key: str
    ip_intel_timeout_seconds: int
    ip_intel_cache_ttl_seconds: int
    auth_failed_login_window_minutes: int
    auth_failed_login_max_attempts: int
    auth_failed_login_lockout_minutes: int
    user_operation_retention_days: int
    user_device_retention_days: int
    user_login_context_retention_days: int
    user_telemetry_purge_on_startup: bool

    nowpayments_enabled: bool
    nowpayments_api_base: str
    nowpayments_api_key: str
    nowpayments_ipn_secret: str
    nowpayments_success_url: str
    nowpayments_cancel_url: str
    nowpayments_partial_url: str
    nowpayments_donation_widget_url: str
    nowpayments_donation_link_url: str
    public_docs_url: str
    billing_db_path: str
    nowpayments_plan_catalog: dict[str, float]
    nowpayments_pay_currencies: list[dict[str, str]]

    support_triage_provider: str
    support_triage_api_key: str
    support_triage_webhook_url: str
    support_triage_webhook_secret: str
    support_ticket_db_path: str
    status_db_path: str
    risk_job_db_path: str
    support_smtp_host: str
    support_smtp_port: int
    support_smtp_username: str
    support_smtp_password: str
    support_smtp_use_tls: bool
    support_smtp_use_ssl: bool
    account_email_from: str
    account_email_subject_prefix: str
    support_email_from: str
    support_email_notify_to: str
    support_email_subject_prefix: str
    support_inbound_reply_to: str
    support_inbound_routing_active: bool
    support_agent_emails: List[str]
    support_inbound_webhook_secret: str
    support_resend_api_key: str
    support_resend_fetch_timeout_seconds: int
    support_resend_sync_unmapped_alert_threshold: int
    support_resend_sync_unmapped_sustained_runs: int
    support_ticket_attachments_dir: str
    support_ticket_attachment_max_files: int
    support_ticket_attachment_max_bytes: int
    support_ticket_attachment_scan_clamav: bool
    status_sampler_secret: str
    risk_worker_shared_secret: str
    support_rate_limit_ip_per_5m: int
    support_rate_limit_email_per_5m: int
    support_rate_limit_ip_per_hour: int
    support_rate_limit_email_per_hour: int
    account_security_code_expiry_minutes: int
    account_security_code_resend_cooldown_seconds: int
    password_reset_expiry_minutes: int
    signup_code_expiry_minutes: int
    signup_code_resend_cooldown_seconds: int
    turnstile_site_key: str
    turnstile_secret_key: str
    turnstile_enforce: bool
    web_portal_public_base_url: str
    web_portal_app_base_url: str
    web_portal_marketing_base_url: str
    session_cookie_domain: str
    session_cookie_name: str
    email_brand_logo_url: str
    support_slack_enabled: bool
    support_slack_webhook_url: str
    support_slack_timeout_seconds: int
    support_bug_cursor_enabled: bool
    support_bug_cursor_post_mode: str
    support_bug_cursor_webhook_url: str
    support_bug_cursor_user_token: str
    support_bug_cursor_channel_id: str
    support_bug_cursor_mention: str
    support_bug_cursor_timeout_seconds: int
    slack_events_signing_secret: str
    slack_bot_token: str
    slack_github_pull_requests_channel_id: str
    slack_github_approver_user_ids: List[str]
    github_token: str
    github_owner: str
    github_repo: str
    github_slack_auto_merge: bool
    github_slack_merge_method: str
    github_slack_delete_branch: bool
    trustpilot_webhook_secret: str
    trustpilot_slack_enabled: bool
    trustpilot_slack_webhook_url: str
    trustpilot_slack_timeout_seconds: int


def load_settings() -> Settings:
    local_default_db = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "web_portal_auth.db",
    )
    support_default_db = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "support_tickets.db",
    )
    status_default_db = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "status_metrics.db",
    )
    risk_job_default_db = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "risk_jobs.db",
    )
    support_attachments_default_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "support_attachments",
    )
    billing_default_db = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "billing.db",
    )
    auth_db_default = os.getenv("WEB_PORTAL_AUTH_DB", local_default_db)
    support_email_notify_to = os.getenv("SUPPORT_EMAIL_NOTIFY_TO", "support@hodler-suite.com")
    support_email_from = os.getenv("SUPPORT_EMAIL_FROM", "support@hodler-suite.com")
    support_inbound_reply_to = os.getenv("SUPPORT_INBOUND_REPLY_TO", support_email_notify_to)
    account_email_from = os.getenv("ACCOUNT_EMAIL_FROM", "no_reply@hodler-suite.com")
    support_agent_emails_default = ",".join(
        [item for item in [support_email_notify_to, support_email_from] if str(item).strip()]
    )
    turnstile_site_key = os.getenv("TURNSTILE_SITE_KEY", "").strip()
    turnstile_secret_key = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    turnstile_enforce_raw = os.getenv("TURNSTILE_ENFORCE")
    if turnstile_enforce_raw is None or not str(turnstile_enforce_raw).strip():
        # Auto-enable when both keys are configured unless explicitly disabled.
        turnstile_enforce_requested = bool(turnstile_site_key and turnstile_secret_key)
    else:
        turnstile_enforce_requested = _to_bool(str(turnstile_enforce_raw), default=False)
    turnstile_enforce = bool(turnstile_enforce_requested and turnstile_site_key and turnstile_secret_key)
    plan_catalog = _to_plan_catalog(os.getenv("NOWPAYMENTS_PLAN_CATALOG", ""))
    if not plan_catalog:
        plan_catalog = {
            "basic-monthly": 49.99,
            "pro-monthly": 299.99,
        }
    pay_currency_options = _to_pay_currency_options(os.getenv("NOWPAYMENTS_PAY_CURRENCIES", ""))
    risk_worker_shared_secret = os.getenv(
        "RISK_WORKER_SHARED_SECRET",
        os.getenv("WEBHOOK_SHARED_SECRET", ""),
    ).strip()
    web_portal_public_base_url = _normalize_base_url(
        os.getenv("WEB_PORTAL_PUBLIC_BASE_URL", "https://app.hodler-suite.com")
    )
    if not web_portal_public_base_url:
        web_portal_public_base_url = "https://app.hodler-suite.com"

    web_portal_app_base_url = _normalize_base_url(
        os.getenv("WEB_PORTAL_APP_BASE_URL", web_portal_public_base_url)
    )
    if not web_portal_app_base_url:
        web_portal_app_base_url = web_portal_public_base_url

    marketing_base_url_raw = os.getenv("WEB_PORTAL_MARKETING_BASE_URL", "").strip()
    web_portal_marketing_base_url = _normalize_base_url(marketing_base_url_raw)
    if not web_portal_marketing_base_url:
        web_portal_marketing_base_url = _derive_marketing_base_url_from_app(web_portal_app_base_url)

    app_host = str(urlparse(web_portal_app_base_url).hostname or "").strip().lower()
    marketing_host = str(urlparse(web_portal_marketing_base_url).hostname or "").strip().lower()
    explicit_cookie_domain = _normalize_cookie_domain(os.getenv("WEB_PORTAL_SESSION_COOKIE_DOMAIN", ""))
    derived_cookie_domain = _derive_cookie_domain(
        web_portal_app_base_url,
        web_portal_marketing_base_url,
    )
    if explicit_cookie_domain and _cookie_domain_covers_hosts(explicit_cookie_domain, app_host, marketing_host):
        session_cookie_domain = explicit_cookie_domain
    elif derived_cookie_domain and _cookie_domain_covers_hosts(derived_cookie_domain, app_host, marketing_host):
        session_cookie_domain = derived_cookie_domain
    else:
        session_cookie_domain = explicit_cookie_domain or derived_cookie_domain

    session_cookie_name = str(os.getenv("WEB_PORTAL_SESSION_COOKIE_NAME", "hs_portal_session")).strip()
    if not session_cookie_name:
        session_cookie_name = "hs_portal_session"
    email_brand_logo_url = os.getenv("EMAIL_BRAND_LOGO_URL", "").strip()
    if not email_brand_logo_url:
        email_brand_logo_url = f"{web_portal_public_base_url}/static/brand/hodler-suite-email-logo.png"

    ip_intel_api_key = os.getenv("IP_INTEL_API_KEY", "").strip()
    ip_intel_lookup_url = os.getenv("IP_INTEL_LOOKUP_URL", "").strip()
    if not ip_intel_lookup_url:
        ip_intel_lookup_url = _default_ip_intel_lookup_url(ip_intel_api_key)

    return Settings(
        secret_key=os.getenv("WEB_PORTAL_SECRET_KEY", "change-this-in-production"),
        force_https=_to_bool(os.getenv("WEB_PORTAL_FORCE_HTTPS"), default=False),
        allowed_origins=_to_list(os.getenv("WEB_PORTAL_ALLOWED_ORIGINS", "")),
        auth_db_path=auth_db_default,
        auth_2fa_issuer=os.getenv("AUTH_2FA_ISSUER", "Hodler Suite"),
        master_account_email=os.getenv("MASTER_ACCOUNT_EMAIL", "admin@hodler-suite.com"),
        master_account_password=os.getenv("MASTER_ACCOUNT_PASSWORD", "change-master-password-now"),
        session_idle_minutes=max(5, _to_int(os.getenv("SESSION_IDLE_MINUTES", "720"), 720)),
        sensitive_ops_require_2fa=_to_bool(os.getenv("SENSITIVE_OPS_REQUIRE_2FA"), default=False),
        auth_anomaly_prompt_enabled=_to_bool(os.getenv("AUTH_ANOMALY_PROMPT_ENABLED"), default=True),
        ip_intel_lookup_url=ip_intel_lookup_url,
        ip_intel_api_key=ip_intel_api_key,
        ip_intel_timeout_seconds=max(2, _to_int(os.getenv("IP_INTEL_TIMEOUT_SECONDS", "4"), 4)),
        ip_intel_cache_ttl_seconds=max(30, _to_int(os.getenv("IP_INTEL_CACHE_TTL_SECONDS", "300"), 300)),
        auth_failed_login_window_minutes=max(
            1,
            _to_int(os.getenv("AUTH_FAILED_LOGIN_WINDOW_MINUTES", "15"), 15),
        ),
        auth_failed_login_max_attempts=max(
            1,
            _to_int(os.getenv("AUTH_FAILED_LOGIN_MAX_ATTEMPTS", "6"), 6),
        ),
        auth_failed_login_lockout_minutes=max(
            1,
            _to_int(os.getenv("AUTH_FAILED_LOGIN_LOCKOUT_MINUTES", "15"), 15),
        ),
        user_operation_retention_days=max(
            7,
            _to_int(os.getenv("USER_OPERATION_RETENTION_DAYS", "180"), 180),
        ),
        user_device_retention_days=max(
            7,
            _to_int(os.getenv("USER_DEVICE_RETENTION_DAYS", "180"), 180),
        ),
        user_login_context_retention_days=max(
            7,
            _to_int(os.getenv("USER_LOGIN_CONTEXT_RETENTION_DAYS", "90"), 90),
        ),
        user_telemetry_purge_on_startup=_to_bool(os.getenv("USER_TELEMETRY_PURGE_ON_STARTUP"), default=True),
        nowpayments_enabled=_to_bool(os.getenv("NOWPAYMENTS_ENABLED"), default=False),
        nowpayments_api_base=os.getenv("NOWPAYMENTS_API_BASE", "https://api.nowpayments.io/v1"),
        nowpayments_api_key=os.getenv("NOWPAYMENTS_API_KEY", ""),
        nowpayments_ipn_secret=os.getenv("NOWPAYMENTS_IPN_SECRET", ""),
        nowpayments_success_url=os.getenv("NOWPAYMENTS_SUCCESS_URL", ""),
        nowpayments_cancel_url=os.getenv("NOWPAYMENTS_CANCEL_URL", ""),
        nowpayments_partial_url=os.getenv("NOWPAYMENTS_PARTIAL_URL", ""),
        nowpayments_donation_widget_url=os.getenv("NOWPAYMENTS_DONATION_WIDGET_URL", "").strip(),
        nowpayments_donation_link_url=os.getenv("NOWPAYMENTS_DONATION_LINK_URL", "").strip(),
        public_docs_url=os.getenv("PUBLIC_DOCS_URL", "").strip(),
        billing_db_path=os.getenv("WEB_PORTAL_BILLING_DB", billing_default_db),
        nowpayments_plan_catalog=plan_catalog,
        nowpayments_pay_currencies=pay_currency_options,
        support_triage_provider=os.getenv("SUPPORT_TRIAGE_PROVIDER", "disabled"),
        support_triage_api_key=os.getenv("SUPPORT_TRIAGE_API_KEY", ""),
        support_triage_webhook_url=os.getenv("SUPPORT_TRIAGE_WEBHOOK_URL", ""),
        support_triage_webhook_secret=os.getenv("SUPPORT_TRIAGE_WEBHOOK_SECRET", ""),
        support_ticket_db_path=os.getenv("WEB_PORTAL_SUPPORT_DB", support_default_db),
        status_db_path=os.getenv("WEB_PORTAL_STATUS_DB", status_default_db),
        risk_job_db_path=os.getenv("WEB_PORTAL_RISK_JOB_DB", risk_job_default_db),
        support_smtp_host=os.getenv("SUPPORT_SMTP_HOST", ""),
        support_smtp_port=max(1, _to_int(os.getenv("SUPPORT_SMTP_PORT", "587"), 587)),
        support_smtp_username=os.getenv("SUPPORT_SMTP_USERNAME", ""),
        support_smtp_password=os.getenv("SUPPORT_SMTP_PASSWORD", ""),
        support_smtp_use_tls=_to_bool(os.getenv("SUPPORT_SMTP_USE_TLS"), default=True),
        support_smtp_use_ssl=_to_bool(os.getenv("SUPPORT_SMTP_USE_SSL"), default=False),
        account_email_from=account_email_from,
        account_email_subject_prefix=os.getenv("ACCOUNT_EMAIL_SUBJECT_PREFIX", "[Hodler Suite]"),
        support_email_from=support_email_from,
        support_email_notify_to=support_email_notify_to,
        support_email_subject_prefix=os.getenv("SUPPORT_EMAIL_SUBJECT_PREFIX", "[Hodler Suite]"),
        support_inbound_reply_to=support_inbound_reply_to,
        support_inbound_routing_active=_to_bool(os.getenv("SUPPORT_INBOUND_ROUTING_ACTIVE"), default=False),
        support_agent_emails=_to_list(os.getenv("SUPPORT_AGENT_EMAILS", support_agent_emails_default)),
        support_inbound_webhook_secret=os.getenv("SUPPORT_INBOUND_WEBHOOK_SECRET", ""),
        support_resend_api_key=os.getenv("SUPPORT_RESEND_API_KEY", ""),
        support_resend_fetch_timeout_seconds=max(
            3, _to_int(os.getenv("SUPPORT_RESEND_FETCH_TIMEOUT_SECONDS", "15"), 15)
        ),
        support_resend_sync_unmapped_alert_threshold=max(
            0,
            _to_int(os.getenv("SUPPORT_RESEND_SYNC_UNMAPPED_ALERT_THRESHOLD", "5"), 5),
        ),
        support_resend_sync_unmapped_sustained_runs=max(
            2,
            _to_int(os.getenv("SUPPORT_RESEND_SYNC_UNMAPPED_SUSTAINED_RUNS", "3"), 3),
        ),
        support_ticket_attachments_dir=os.getenv(
            "SUPPORT_TICKET_ATTACHMENTS_DIR",
            support_attachments_default_dir,
        ).strip()
        or support_attachments_default_dir,
        support_ticket_attachment_max_files=max(
            1,
            min(10, _to_int(os.getenv("SUPPORT_TICKET_ATTACHMENT_MAX_FILES", "5"), 5)),
        ),
        support_ticket_attachment_max_bytes=max(
            1 * 1024 * 1024,
            min(
                100 * 1024 * 1024,
                _to_int(os.getenv("SUPPORT_TICKET_ATTACHMENT_MAX_BYTES", str(25 * 1024 * 1024)), 25 * 1024 * 1024),
            ),
        ),
        support_ticket_attachment_scan_clamav=_to_bool(
            os.getenv("SUPPORT_TICKET_ATTACHMENT_SCAN_CLAMAV"),
            default=True,
        ),
        status_sampler_secret=os.getenv("STATUS_SAMPLER_SECRET", "").strip(),
        risk_worker_shared_secret=risk_worker_shared_secret,
        support_rate_limit_ip_per_5m=max(1, _to_int(os.getenv("SUPPORT_RATE_LIMIT_IP_PER_5M", "6"), 6)),
        support_rate_limit_email_per_5m=max(1, _to_int(os.getenv("SUPPORT_RATE_LIMIT_EMAIL_PER_5M", "3"), 3)),
        support_rate_limit_ip_per_hour=max(1, _to_int(os.getenv("SUPPORT_RATE_LIMIT_IP_PER_HOUR", "30"), 30)),
        support_rate_limit_email_per_hour=max(1, _to_int(os.getenv("SUPPORT_RATE_LIMIT_EMAIL_PER_HOUR", "10"), 10)),
        account_security_code_expiry_minutes=max(
            5, _to_int(os.getenv("ACCOUNT_SECURITY_CODE_EXPIRY_MINUTES", "30"), 30)
        ),
        account_security_code_resend_cooldown_seconds=max(
            0, _to_int(os.getenv("ACCOUNT_SECURITY_CODE_RESEND_COOLDOWN_SECONDS", "60"), 60)
        ),
        password_reset_expiry_minutes=max(5, _to_int(os.getenv("PASSWORD_RESET_EXPIRY_MINUTES", "30"), 30)),
        signup_code_expiry_minutes=max(5, _to_int(os.getenv("SIGNUP_CODE_EXPIRY_MINUTES", "30"), 30)),
        signup_code_resend_cooldown_seconds=max(
            0, _to_int(os.getenv("SIGNUP_CODE_RESEND_COOLDOWN_SECONDS", "60"), 60)
        ),
        turnstile_site_key=turnstile_site_key,
        turnstile_secret_key=turnstile_secret_key,
        turnstile_enforce=turnstile_enforce,
        web_portal_public_base_url=web_portal_public_base_url,
        web_portal_app_base_url=web_portal_app_base_url,
        web_portal_marketing_base_url=web_portal_marketing_base_url,
        session_cookie_domain=session_cookie_domain,
        session_cookie_name=session_cookie_name,
        email_brand_logo_url=email_brand_logo_url,
        support_slack_enabled=_to_bool(os.getenv("SUPPORT_SLACK_ENABLED"), default=False),
        support_slack_webhook_url=os.getenv("SUPPORT_SLACK_WEBHOOK_URL", "").strip(),
        support_slack_timeout_seconds=max(3, _to_int(os.getenv("SUPPORT_SLACK_TIMEOUT_SECONDS", "8"), 8)),
        support_bug_cursor_enabled=_to_bool(os.getenv("SUPPORT_BUG_CURSOR_ENABLED"), default=False),
        support_bug_cursor_post_mode=os.getenv("SUPPORT_BUG_CURSOR_POST_MODE", "webhook").strip().lower()
        or "webhook",
        support_bug_cursor_webhook_url=os.getenv("SUPPORT_BUG_CURSOR_WEBHOOK_URL", "").strip(),
        support_bug_cursor_user_token=os.getenv("SUPPORT_BUG_CURSOR_USER_TOKEN", "").strip(),
        support_bug_cursor_channel_id=os.getenv(
            "SUPPORT_BUG_CURSOR_CHANNEL_ID",
            os.getenv("SLACK_GITHUB_PULL_REQUESTS_CHANNEL_ID", ""),
        ).strip(),
        support_bug_cursor_mention=os.getenv("SUPPORT_BUG_CURSOR_MENTION", "@Cursor").strip() or "@Cursor",
        support_bug_cursor_timeout_seconds=max(3, _to_int(os.getenv("SUPPORT_BUG_CURSOR_TIMEOUT_SECONDS", "8"), 8)),
        slack_events_signing_secret=os.getenv("SLACK_EVENTS_SIGNING_SECRET", "").strip(),
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN", "").strip(),
        slack_github_pull_requests_channel_id=os.getenv("SLACK_GITHUB_PULL_REQUESTS_CHANNEL_ID", "").strip(),
        slack_github_approver_user_ids=_to_list(os.getenv("SLACK_GITHUB_APPROVER_USER_IDS", "")),
        github_token=os.getenv("GITHUB_TOKEN", "").strip(),
        github_owner=os.getenv("GITHUB_OWNER", "").strip(),
        github_repo=os.getenv("GITHUB_REPO", "").strip(),
        github_slack_auto_merge=_to_bool(os.getenv("GITHUB_SLACK_AUTO_MERGE"), default=False),
        github_slack_merge_method=os.getenv("GITHUB_SLACK_MERGE_METHOD", "squash").strip().lower() or "squash",
        github_slack_delete_branch=_to_bool(os.getenv("GITHUB_SLACK_DELETE_BRANCH"), default=True),
        trustpilot_webhook_secret=os.getenv("TRUSTPILOT_WEBHOOK_SECRET", "").strip(),
        trustpilot_slack_enabled=_to_bool(os.getenv("TRUSTPILOT_SLACK_ENABLED"), default=False),
        trustpilot_slack_webhook_url=os.getenv("TRUSTPILOT_SLACK_WEBHOOK_URL", "").strip(),
        trustpilot_slack_timeout_seconds=max(
            3,
            _to_int(os.getenv("TRUSTPILOT_SLACK_TIMEOUT_SECONDS", "8"), 8),
        ),
    )
