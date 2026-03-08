"""Authentication, 2FA, and account-management routes."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parseaddr
import secrets
from sqlite3 import IntegrityError
import uuid
from typing import Optional

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth import (
    get_current_user,
    login_required,
    login_user,
    logout_user,
    pull_safe_next,
    roles_required,
    validate_csrf_token,
)
from ..security_context import (
    country_flag,
    default_ip_intel,
    lookup_ip_intel,
    normalize_region,
    parse_user_agent,
    region_from_country_code,
)
from ..special_accounts import SPECIAL_ENTERPRISE_EMAILS
from ..totp import build_otpauth_uri, generate_totp_secret, verify_totp_code


auth_bp = Blueprint("auth", __name__)
NAME_MAX_LENGTH = 120
EMAIL_MAX_LENGTH = 320


def _normalize_person_name(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _is_valid_email(value: str) -> bool:
    candidate = str(value or "").strip()
    if not candidate or len(candidate) > EMAIL_MAX_LENGTH:
        return False
    parsed = str(parseaddr(candidate)[1] or "").strip()
    if not parsed or len(parsed) > EMAIL_MAX_LENGTH:
        return False
    if parsed != candidate:
        return False
    if parsed.count("@") != 1:
        return False
    local_part, domain_part = parsed.rsplit("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return False
    return True


def _is_placeholder_master_email(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return "__replace_" in normalized or "replace_master_email" in normalized


def _store():
    return current_app.config["USER_STORE"]


def _account_mailer():
    return current_app.config["ACCOUNT_MAILER"]


def _settings():
    return current_app.config["SETTINGS"]


def _auth_failure_policy() -> dict[str, int]:
    settings = _settings()
    window_minutes = max(1, int(getattr(settings, "auth_failed_login_window_minutes", 15) or 15))
    max_attempts = max(1, int(getattr(settings, "auth_failed_login_max_attempts", 6) or 6))
    lockout_minutes = max(1, int(getattr(settings, "auth_failed_login_lockout_minutes", 15) or 15))
    return {
        "window_seconds": window_minutes * 60,
        "max_attempts": max_attempts,
        "lockout_seconds": lockout_minutes * 60,
    }


def _login_lockout_state(*, email: str, ip_address: str) -> dict[str, int | bool | str]:
    policy = _auth_failure_policy()
    return _store().get_login_lockout_state(
        email=email,
        ip_address=ip_address,
        window_seconds=int(policy["window_seconds"]),
        max_failures=int(policy["max_attempts"]),
        lockout_seconds=int(policy["lockout_seconds"]),
    )


def _register_login_failure(
    *,
    email: str,
    ip_address: str,
    reason: str,
    user_id: Optional[int] = None,
) -> dict[str, int | bool | str]:
    policy = _auth_failure_policy()
    return _store().register_login_failure(
        email=email,
        ip_address=ip_address,
        reason=reason,
        user_id=int(user_id) if user_id is not None else None,
        window_seconds=int(policy["window_seconds"]),
        max_failures=int(policy["max_attempts"]),
        lockout_seconds=int(policy["lockout_seconds"]),
    )


def _clear_login_failures(*, email: str, ip_address: str) -> None:
    _store().clear_login_failures(email=email, ip_address=ip_address)


def _lockout_notice(retry_after_seconds: int) -> str:
    retry_seconds = max(1, int(retry_after_seconds or 0))
    retry_minutes = max(1, (retry_seconds + 59) // 60)
    return (
        "Too many failed sign-in attempts from your current network. "
        f"Please retry in about {retry_minutes} minute(s)."
    )


def _apply_special_account_entitlements(user_id: int, email: str) -> None:
    normalized_email = str(email or "").strip().lower()
    if normalized_email not in SPECIAL_ENTERPRISE_EMAILS:
        return
    current_app.config["USER_STORE"].set_active(int(user_id), True)
    current_app.config["BILLING_STORE"].assign_unlimited_enterprise(
        user_id=int(user_id),
        user_email=normalized_email,
        source="special_account_auto",
    )


def _manageable_user_by_uid(actor: dict, target_uid: str):
    normalized_uid = str(target_uid or "").strip()
    if len(normalized_uid) != 8 or not normalized_uid.isdigit():
        return None
    target = _store().get_user_by_uid(normalized_uid)
    if not target:
        return None

    actor_role = str(actor.get("role", "")).strip().lower()
    if actor_role == "master":
        if str(target.get("role", "")).strip().lower() == "master":
            return None
        return target

    if actor_role == "admin":
        if str(target.get("role", "")).strip().lower() != "child":
            return None
        if int(target.get("parent_user_id") or 0) != int(actor.get("id") or 0):
            return None
        return target
    return None


def _clear_pending_signup() -> None:
    session.pop("pending_signup_email", None)
    session.pop("pending_signup_password_hash", None)
    session.pop("pending_signup_profile", None)
    session.pop("pending_signup_context", None)


def _require_csrf_or_redirect(target_endpoint: str) -> Optional[object]:
    token = request.form.get("csrf_token")
    if not validate_csrf_token(token):
        flash("Security token invalid or expired. Please retry.", "error")
        return redirect(url_for(target_endpoint))
    return None


def _deny_child_self_email_change(user: dict | None) -> Optional[object]:
    if not user:
        return redirect(url_for("auth.login"))
    if str(user.get("role", "")).strip().lower() != "child":
        return None
    flash("Email change is managed by support for child accounts. Contact an admin/master account.", "error")
    return redirect(url_for("pages.account_page"))


def _clear_session_cookie_variants(response) -> None:
    cookie_name = str(current_app.config.get("SESSION_COOKIE_NAME", "session") or "session").strip() or "session"
    cookie_names = [cookie_name]
    if cookie_name != "session":
        cookie_names.append("session")
    cookie_path = str(current_app.config.get("SESSION_COOKIE_PATH", "/") or "/").strip() or "/"
    configured_domain = str(current_app.config.get("SESSION_COOKIE_DOMAIN", "") or "").strip()
    request_host = str(request.host or "").split(":", 1)[0].strip().lower()

    candidates: list[str | None] = [None]
    if request_host:
        candidates.append(request_host)
    if configured_domain:
        candidates.append(configured_domain)
        candidates.append(configured_domain.lstrip("."))

    seen: set[str] = set()
    for name in cookie_names:
        for domain in candidates:
            key = f"{name}:{domain or '<none>'}"
            if not key or key in seen:
                continue
            seen.add(key)
            response.delete_cookie(name, path=cookie_path, domain=domain)


def _extract_client_ip() -> str:
    cf_ip = str(request.headers.get("CF-Connecting-IP", "")).strip()
    if cf_ip:
        return cf_ip
    forwarded = str(request.headers.get("X-Forwarded-For", "")).strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return str(request.remote_addr or "").strip()


def _normalize_device_uuid(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return ""


def _ensure_device_uuid() -> str:
    session_value = _normalize_device_uuid(str(session.get("device_uuid", "")))
    cookie_value = _normalize_device_uuid(str(request.cookies.get("hs_device_uuid", "")))
    device_uuid = cookie_value or session_value or str(uuid.uuid4())
    session["device_uuid"] = device_uuid
    return device_uuid


def _request_security_context() -> dict:
    cached = getattr(g, "_request_security_context", None)
    if isinstance(cached, dict):
        return cached

    settings = _settings()
    ip_address = _extract_client_ip()
    device_uuid = _ensure_device_uuid()
    user_agent = str(request.headers.get("User-Agent", "")).strip()
    device = parse_user_agent(user_agent)

    cf_country = str(request.headers.get("CF-IPCountry", "")).strip().upper()
    ip_intel = default_ip_intel(ip_address)
    if len(cf_country) == 2 and cf_country.isalpha() and cf_country not in {"XX", "T1"}:
        ip_intel = dict(ip_intel)
        ip_intel["country_code"] = cf_country
        ip_intel["country_flag"] = country_flag(cf_country)
        if not str(ip_intel.get("country_name", "")).strip():
            ip_intel["country_name"] = "Unknown"
        ip_intel["intel_source"] = "cloudflare_header"

    if str(getattr(settings, "ip_intel_lookup_url", "") or "").strip():
        ip_intel = lookup_ip_intel(
            ip_address=ip_address,
            lookup_url=str(getattr(settings, "ip_intel_lookup_url", "") or "").strip(),
            api_key=str(getattr(settings, "ip_intel_api_key", "") or "").strip(),
            timeout_seconds=int(getattr(settings, "ip_intel_timeout_seconds", 4) or 4),
            cache_ttl_seconds=int(getattr(settings, "ip_intel_cache_ttl_seconds", 300) or 300),
        )

    if (
        (not str(ip_intel.get("country_code", "")).strip() or str(ip_intel.get("country_code", "")).strip().upper() in {"XX", "T1"})
        and len(cf_country) == 2
        and cf_country.isalpha()
        and cf_country not in {"XX", "T1"}
    ):
        ip_intel = dict(ip_intel)
        ip_intel["country_code"] = cf_country
        ip_intel["country_flag"] = country_flag(cf_country)
        if not str(ip_intel.get("country_name", "")).strip():
            ip_intel["country_name"] = "Unknown"
        intel_source = str(ip_intel.get("intel_source", "")).strip().lower()
        if intel_source in {"", "none", "lookup_failed", "invalid_payload"}:
            ip_intel["intel_source"] = "cloudflare_header"

    context = {
        "ip_address": str(ip_intel.get("ip_address", "")).strip() or ip_address,
        "device_uuid": device_uuid,
        "device_type": str(device.get("device_type", "")).strip(),
        "os_name": str(device.get("os_name", "")).strip(),
        "os_version": str(device.get("os_version", "")).strip(),
        "browser_name": str(device.get("browser_name", "")).strip(),
        "browser_version": str(device.get("browser_version", "")).strip(),
        "country_code": str(ip_intel.get("country_code", "")).strip().upper(),
        "country_name": str(ip_intel.get("country_name", "")).strip(),
        "country_flag": str(ip_intel.get("country_flag", "")).strip(),
        "is_vpn": ip_intel.get("is_vpn"),
        "is_residential_proxy": ip_intel.get("is_residential_proxy"),
        "is_other_proxy": ip_intel.get("is_other_proxy"),
        "is_datacenter": ip_intel.get("is_datacenter"),
        "is_hosting": ip_intel.get("is_hosting"),
        "intel_source": str(ip_intel.get("intel_source", "")).strip(),
    }
    g._request_security_context = context
    return context


def _record_user_operation(
    *,
    user_id: int,
    operation_type: str,
    target_user_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    try:
        _store().record_user_operation(
            user_id=int(user_id),
            operation_type=operation_type,
            context=_request_security_context(),
            target_user_id=int(target_user_id) if target_user_id is not None else None,
            details=details or {},
        )
    except Exception:
        current_app.logger.exception(
            "record_user_operation_failed op=%s user_id=%s target_user_id=%s",
            operation_type,
            user_id,
            target_user_id,
        )


def _apply_login_anomaly_prompt(user: dict) -> None:
    settings = _settings()
    if not bool(getattr(settings, "auth_anomaly_prompt_enabled", True)):
        return
    try:
        security_context = _request_security_context()
        context = _store().record_login_context(
            user_id=int(user["id"]),
            ip_address=str(security_context.get("ip_address", "")).strip(),
            user_agent=str(request.headers.get("User-Agent", "")).strip(),
        )
        if bool(context.get("is_new_device")):
            flash("Security notice: new device/browser sign-in detected for your account.", "info")
        elif bool(context.get("is_new_ip")):
            flash("Security notice: sign-in detected from a new IP/network.", "info")
    except Exception:
        current_app.logger.exception("login_anomaly_prompt_failed user_id=%s", int(user.get("id") or 0))


def _complete_login(user: dict, next_target: str, *, show_success_flash: bool = True) -> object:
    _ensure_device_uuid()
    login_user(int(user["id"]))
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="login_success",
        details={"next_target": str(next_target or "").strip()},
    )
    _apply_login_anomaly_prompt(user)
    if show_success_flash:
        flash("Signed in successfully.", "success")
    return redirect(next_target)


def _step_up_policy_enabled() -> bool:
    return bool(getattr(_settings(), "sensitive_ops_require_2fa", False))


def _require_step_up_or_redirect(user: dict | None, *, target_endpoint: str) -> Optional[object]:
    if not _step_up_policy_enabled():
        return None
    if not user:
        return redirect(url_for("auth.login"))
    if not bool(user.get("totp_enabled")):
        flash("This action requires 2FA. Enable 2FA first or disable step-up policy.", "error")
        return redirect(url_for(target_endpoint))

    code = str(request.form.get("step_up_code", "")).strip()
    if not verify_totp_code(str(user.get("totp_secret") or ""), code):
        _record_user_operation(
            user_id=int(user["id"]),
            operation_type="step_up_failed",
            details={"target_endpoint": str(target_endpoint or ""), "request_endpoint": str(request.endpoint or "")},
        )
        flash("Step-up 2FA code is invalid.", "error")
        return redirect(url_for(target_endpoint))
    return None


def _require_totp_code_or_redirect(
    user: dict | None,
    *,
    target_endpoint: str,
    code_field: str,
    operation_name: str,
) -> Optional[object]:
    if not user:
        return redirect(url_for("auth.login"))
    if not bool(user.get("totp_enabled")):
        flash("This operation requires 2FA. Enable 2FA on your account before continuing.", "error")
        return redirect(url_for(target_endpoint))

    code = str(request.form.get(code_field, "")).strip()
    if len(code) != 6 or not code.isdigit() or not verify_totp_code(str(user.get("totp_secret") or ""), code):
        _record_user_operation(
            user_id=int(user["id"]),
            operation_type="step_up_failed",
            details={
                "target_endpoint": str(target_endpoint or ""),
                "request_endpoint": str(request.endpoint or ""),
                "operation_name": str(operation_name or "").strip(),
            },
        )
        flash("2FA code is invalid.", "error")
        return redirect(url_for(target_endpoint))
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("pages.dashboard"))

    if request.method == "GET":
        notice = str(session.pop("session_security_notice", "")).strip()
        if notice:
            flash(notice, "info")
        return render_template("auth/login.html", next_target=pull_safe_next())

    csrf_redirect = _require_csrf_or_redirect("auth.login")
    if csrf_redirect:
        return csrf_redirect

    email = str(request.form.get("email", "")).strip().lower()
    password = str(request.form.get("password", ""))
    next_target = pull_safe_next()
    if not email:
        flash("Invalid credentials.", "error")
        return render_template("auth/login.html", next_target=next_target), 401
    client_ip = _extract_client_ip()
    if email:
        lockout_state = _login_lockout_state(email=email, ip_address=client_ip)
        if bool(lockout_state.get("locked")):
            retry_after_seconds = int(lockout_state.get("retry_after_seconds") or 0)
            locked_user = _store().get_user_by_email(email)
            if locked_user:
                _record_user_operation(
                    user_id=int(locked_user["id"]),
                    operation_type="login_blocked_lockout",
                    details={
                        "ip_address": client_ip,
                        "retry_after_seconds": retry_after_seconds,
                        "failure_count": int(lockout_state.get("failure_count") or 0),
                    },
                )
            flash(_lockout_notice(retry_after_seconds), "error")
            return render_template("auth/login.html", next_target=next_target), 429

    user = _store().get_user_by_email(email)
    password_ok = bool(user and check_password_hash(user["password_hash"], password))
    if not user or not user.get("is_active", False) or not password_ok:
        reason = "invalid_credentials"
        if user and not bool(user.get("is_active", False)):
            reason = "inactive_account"
        elif user and not password_ok:
            reason = "invalid_password"
        failure_state = _register_login_failure(
            email=email,
            ip_address=client_ip,
            reason=reason,
            user_id=int(user["id"]) if user else None,
        )
        if user:
            _record_user_operation(
                user_id=int(user["id"]),
                operation_type="login_failed",
                details={
                    "reason": reason,
                    "ip_address": client_ip,
                    "failure_count": int(failure_state.get("failure_count") or 0),
                    "locked": bool(failure_state.get("locked")),
                    "retry_after_seconds": int(failure_state.get("retry_after_seconds") or 0),
                },
            )
        if bool(failure_state.get("locked")):
            flash(_lockout_notice(int(failure_state.get("retry_after_seconds") or 0)), "error")
            return render_template("auth/login.html", next_target=next_target), 429
        flash("Invalid credentials.", "error")
        return render_template("auth/login.html", next_target=next_target), 401

    _clear_login_failures(email=email, ip_address=client_ip)

    role = str(user.get("role", "")).strip().lower()
    if role == "child":
        access = current_app.config["BILLING_STORE"].is_user_access_active(user_id=int(user["id"]))
        if not bool(access.get("allowed")):
            _store().set_active(int(user["id"]), False)
            reason = str(access.get("reason", "subscription_inactive"))
            if reason == "subscription_expired":
                flash("Your plan has expired. Contact support to reactivate your account.", "error")
            else:
                flash("Your subscription is inactive. Contact support to restore access.", "error")
            return render_template("auth/login.html", next_target=next_target), 403

    if user.get("totp_enabled"):
        session["pre_2fa_user_id"] = int(user["id"])
        session["post_login_next"] = next_target
        return redirect(url_for("auth.two_factor_challenge"))

    return _complete_login(user, next_target)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if get_current_user():
        return redirect(url_for("pages.dashboard"))

    if request.method == "GET":
        pending_email = str(session.get("pending_signup_email", "")).strip().lower()
        pending_profile = session.get("pending_signup_profile", {})
        if not isinstance(pending_profile, dict):
            pending_profile = {}
        return render_template("auth/signup.html", email=pending_email, signup_profile=pending_profile)

    csrf_redirect = _require_csrf_or_redirect("auth.signup")
    if csrf_redirect:
        return csrf_redirect

    email = str(request.form.get("email", "")).strip().lower()
    password = str(request.form.get("password", ""))
    confirm_password = str(request.form.get("confirm_password", ""))
    first_name = _normalize_person_name(str(request.form.get("first_name", "")))
    last_name = _normalize_person_name(str(request.form.get("last_name", "")))
    date_of_birth = str(request.form.get("date_of_birth", "")).strip()
    gender = str(request.form.get("gender", "")).strip().lower()
    base_region = normalize_region(str(request.form.get("base_region", "")).strip())
    is_corporate_account = str(request.form.get("is_corporate_account", "")).strip().lower() in {"1", "true", "yes", "on"}

    form_profile = {
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "gender": gender,
        "base_region": base_region,
        "is_corporate_account": is_corporate_account,
    }

    if not _is_valid_email(email):
        flash("Please provide a valid email address.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400

    if len(first_name) > NAME_MAX_LENGTH or len(last_name) > NAME_MAX_LENGTH:
        flash(f"Name and surname must be at most {NAME_MAX_LENGTH} characters.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400

    if len(password) < 12:
        flash("Password must be at least 12 characters.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400

    if password != confirm_password:
        flash("Password confirmation does not match.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400

    if not first_name or not last_name:
        flash("Name and surname are required.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400

    try:
        dob_dt = datetime.strptime(date_of_birth, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        flash("Date of birth must be in YYYY-MM-DD format.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400
    if dob_dt >= datetime.now(timezone.utc):
        flash("Date of birth cannot be in the future.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400

    allowed_genders = {"female", "male", "non_binary", "other", "prefer_not_to_say"}
    if gender not in allowed_genders:
        flash("Please select a valid gender option.", "error")
        return render_template("auth/signup.html", email=email, signup_profile=form_profile), 400

    existing = _store().get_user_by_email(email)
    if existing:
        flash("An account with this email already exists. Please sign in.", "error")
        return redirect(url_for("auth.login"))

    registration_context = _request_security_context()
    if base_region == "OTHER":
        inferred_region = region_from_country_code(str(registration_context.get("country_code", "")))
        if inferred_region in {"EU", "US"}:
            form_profile["base_region"] = inferred_region

    session["pending_signup_email"] = email
    session["pending_signup_password_hash"] = generate_password_hash(password)
    session["pending_signup_profile"] = form_profile
    session["pending_signup_context"] = registration_context
    flash("Sign-up started. Click 'Send Confirmation Code' to receive your 6-digit code.", "info")
    return redirect(url_for("auth.signup_verify"))


@auth_bp.route("/signup/verify", methods=["GET", "POST"])
def signup_verify():
    if get_current_user():
        return redirect(url_for("pages.dashboard"))

    pending_email = str(session.get("pending_signup_email", "")).strip().lower()
    pending_password_hash = str(session.get("pending_signup_password_hash", ""))
    pending_profile = session.get("pending_signup_profile", {})
    pending_context = session.get("pending_signup_context", {})
    if not isinstance(pending_profile, dict):
        pending_profile = {}
    if not isinstance(pending_context, dict):
        pending_context = {}
    if not pending_email or not pending_password_hash:
        flash("Sign-up session not found. Please start again.", "error")
        return redirect(url_for("auth.signup"))

    settings = current_app.config["SETTINGS"]
    if request.method == "GET":
        return render_template(
            "auth/signup_verify.html",
            email=pending_email,
            expiry_minutes=settings.signup_code_expiry_minutes,
        )

    csrf_redirect = _require_csrf_or_redirect("auth.signup_verify")
    if csrf_redirect:
        return csrf_redirect

    code = str(request.form.get("code", "")).strip()
    if len(code) != 6 or not code.isdigit():
        flash("Please enter a valid 6-digit confirmation code.", "error")
        return redirect(url_for("auth.signup_verify"))

    verification = _store().consume_email_verification_code(email=pending_email, code=code)
    status = str(verification.get("status", "invalid"))
    if status == "missing":
        flash("No code found. Please click 'Send Confirmation Code' first.", "error")
        return redirect(url_for("auth.signup_verify"))
    if status == "expired":
        flash("Code expired. Click 'Send Confirmation Code' to request a new one.", "error")
        return redirect(url_for("auth.signup_verify"))
    if status != "verified":
        flash("Invalid confirmation code.", "error")
        return redirect(url_for("auth.signup_verify"))

    existing = _store().get_user_by_email(pending_email)
    if existing:
        _clear_pending_signup()
        flash("Account already exists. Please sign in.", "info")
        return redirect(url_for("auth.login"))

    try:
        user_id = _store().create_user(
            email=pending_email,
            password_hash=pending_password_hash,
            role="child",
            parent_user_id=None,
            created_by_user_id=None,
            email_verified=True,
            first_name=str(pending_profile.get("first_name", "")).strip(),
            last_name=str(pending_profile.get("last_name", "")).strip(),
        )
    except IntegrityError:
        _clear_pending_signup()
        flash("Account already exists. Please sign in.", "info")
        return redirect(url_for("auth.login"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.signup"))

    _store().update_registration_profile(
        user_id=int(user_id),
        date_of_birth=str(pending_profile.get("date_of_birth", "")).strip(),
        gender=str(pending_profile.get("gender", "")).strip().lower(),
        is_corporate_account=bool(pending_profile.get("is_corporate_account", False)),
        base_region=normalize_region(str(pending_profile.get("base_region", "")).strip()),
        registration_context=pending_context,
    )
    try:
        _store().record_user_operation(
            user_id=int(user_id),
            operation_type="signup_verified",
            context=pending_context,
            details={"source": "self_signup"},
        )
    except Exception:
        current_app.logger.exception("signup_operation_log_failed user_id=%s", user_id)
    _apply_special_account_entitlements(int(user_id), pending_email)
    login_user(int(user_id))
    _record_user_operation(
        user_id=int(user_id),
        operation_type="login_success",
        details={"source": "signup_autologin"},
    )
    created_user = _store().get_user_by_id(int(user_id))
    if created_user:
        _apply_login_anomaly_prompt(created_user)
    _clear_pending_signup()

    welcome = _account_mailer().send_welcome_email(email=pending_email)
    if welcome.get("sent"):
        flash("Email verified. Welcome to Hodler Suite.", "success")
    else:
        flash("Email verified and account created. Welcome email could not be sent.", "info")

    return redirect(url_for("pages.dashboard"))


@auth_bp.post("/signup/verify/send-code")
def signup_send_code():
    if get_current_user():
        return redirect(url_for("pages.dashboard"))

    csrf_redirect = _require_csrf_or_redirect("auth.signup_verify")
    if csrf_redirect:
        return csrf_redirect

    pending_email = str(session.get("pending_signup_email", "")).strip().lower()
    pending_password_hash = str(session.get("pending_signup_password_hash", ""))
    if not pending_email or not pending_password_hash:
        flash("Sign-up session not found. Please start again.", "error")
        return redirect(url_for("auth.signup"))

    settings = current_app.config["SETTINGS"]
    retry_after = _store().verification_send_retry_after(
        email=pending_email,
        cooldown_seconds=settings.signup_code_resend_cooldown_seconds,
    )
    if retry_after > 0:
        flash(f"Please wait {retry_after} seconds before requesting another code.", "info")
        return redirect(url_for("auth.signup_verify"))

    code = f"{secrets.randbelow(1_000_000):06d}"
    sent = _account_mailer().send_signup_code(
        email=pending_email,
        code=code,
        expires_minutes=settings.signup_code_expiry_minutes,
    )
    if not sent.get("sent"):
        flash("Unable to send confirmation code right now. Please retry shortly.", "error")
        return redirect(url_for("auth.signup_verify"))

    _store().create_email_verification_code(
        email=pending_email,
        code=code,
        expiry_minutes=settings.signup_code_expiry_minutes,
    )
    flash(
        f"Confirmation code sent to {pending_email}. The code expires in {settings.signup_code_expiry_minutes} minutes.",
        "success",
    )
    return redirect(url_for("auth.signup_verify"))


@auth_bp.route("/password-reset", methods=["GET", "POST"])
def password_reset_request():
    if request.method == "GET":
        return render_template("auth/password_reset_request.html")

    csrf_redirect = _require_csrf_or_redirect("auth.password_reset_request")
    if csrf_redirect:
        return csrf_redirect

    email = str(request.form.get("email", "")).strip().lower()
    settings = _settings()
    user = _store().get_user_by_email(email) if "@" in email and "." in email else None
    if user and user.get("is_active"):
        retry_after = _store().password_reset_retry_after(
            email=email,
            cooldown_seconds=settings.account_security_code_resend_cooldown_seconds,
        )
        if retry_after <= 0:
            token_secret = secrets.token_urlsafe(24)
            token_row = _store().create_password_reset_token(
                user_id=int(user["id"]),
                email=email,
                token_secret=token_secret,
                expiry_minutes=settings.password_reset_expiry_minutes,
            )
            reset_token = f"{token_row['id']}.{token_secret}"
            reset_url = url_for("auth.password_reset_confirm", token=reset_token, _external=True)
            _account_mailer().send_password_reset_email(
                email=email,
                reset_url=reset_url,
                expires_minutes=settings.password_reset_expiry_minutes,
            )

    flash(
        "If an active account exists for that email, a password reset link has been sent.",
        "success",
    )
    return redirect(url_for("auth.login"))


@auth_bp.route("/password-reset/confirm", methods=["GET", "POST"])
def password_reset_confirm():
    token = str(request.values.get("token", "")).strip()
    if request.method == "GET":
        return render_template("auth/password_reset_confirm.html", token=token)

    csrf_redirect = _require_csrf_or_redirect("auth.password_reset_request")
    if csrf_redirect:
        return csrf_redirect

    new_password = str(request.form.get("new_password", ""))
    confirm_password = str(request.form.get("confirm_password", ""))
    if len(new_password) < 12:
        flash("New password must be at least 12 characters.", "error")
        return render_template("auth/password_reset_confirm.html", token=token), 400
    if new_password != confirm_password:
        flash("Password confirmation does not match.", "error")
        return render_template("auth/password_reset_confirm.html", token=token), 400

    verification = _store().consume_password_reset_token(token=token)
    status = str(verification.get("status", "invalid"))
    if status == "missing":
        flash("Reset token not found or already used.", "error")
        return render_template("auth/password_reset_confirm.html", token=token), 400
    if status == "expired":
        flash("Reset token expired. Please request a new one.", "error")
        return render_template("auth/password_reset_confirm.html", token=token), 400
    if status != "verified":
        flash("Invalid reset token.", "error")
        return render_template("auth/password_reset_confirm.html", token=token), 400

    user_id = int(verification["user_id"])
    email = str(verification["email"]).strip().lower()
    _store().update_password_hash(user_id, generate_password_hash(new_password))
    _store().bump_session_version(user_id=user_id)
    _record_user_operation(
        user_id=user_id,
        operation_type="password_reset_completed",
        details={"channel": "email_link"},
    )
    _account_mailer().send_password_changed_notice(email=email)
    flash("Password updated successfully. You can now sign in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/2fa/challenge", methods=["GET", "POST"])
def two_factor_challenge():
    pending_id = session.get("pre_2fa_user_id")
    if pending_id is None:
        return redirect(url_for("auth.login"))

    user = _store().get_user_by_id(int(pending_id))
    if not user or not user.get("totp_enabled"):
        session.pop("pre_2fa_user_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("auth/two_factor_challenge.html", email=user["email"])

    csrf_token = str(request.form.get("csrf_token", "")).strip()
    if not validate_csrf_token(csrf_token):
        flash("Security token invalid or expired. Please retry.", "error")
        return render_template("auth/two_factor_challenge.html", email=user["email"]), 400

    email = str(user.get("email", "")).strip().lower()
    client_ip = _extract_client_ip()
    lockout_state = _login_lockout_state(email=email, ip_address=client_ip)
    if bool(lockout_state.get("locked")):
        retry_after_seconds = int(lockout_state.get("retry_after_seconds") or 0)
        session.pop("pre_2fa_user_id", None)
        _record_user_operation(
            user_id=int(user["id"]),
            operation_type="login_2fa_blocked_lockout",
            details={
                "ip_address": client_ip,
                "retry_after_seconds": retry_after_seconds,
                "failure_count": int(lockout_state.get("failure_count") or 0),
            },
        )
        flash(_lockout_notice(retry_after_seconds), "error")
        return redirect(url_for("auth.login"))

    raw_code = str(request.form.get("code", "")).strip()
    code = "".join(ch for ch in raw_code if ch.isdigit())
    if not verify_totp_code(str(user.get("totp_secret") or ""), code, window=2):
        current_app.logger.warning(
            "2fa_login_verify_failed user_id=%s code_length=%s host=%s",
            int(user["id"]),
            len(code),
            str(request.host or "").strip().lower(),
        )
        failure_state = _register_login_failure(
            email=email,
            ip_address=client_ip,
            reason="invalid_2fa_code",
            user_id=int(user["id"]),
        )
        _record_user_operation(
            user_id=int(user["id"]),
            operation_type="login_2fa_failed",
            details={
                "ip_address": client_ip,
                "failure_count": int(failure_state.get("failure_count") or 0),
                "locked": bool(failure_state.get("locked")),
                "retry_after_seconds": int(failure_state.get("retry_after_seconds") or 0),
            },
        )
        if bool(failure_state.get("locked")):
            session.pop("pre_2fa_user_id", None)
            flash(_lockout_notice(int(failure_state.get("retry_after_seconds") or 0)), "error")
            return redirect(url_for("auth.login"))
        flash("Invalid 2FA code.", "error")
        return render_template("auth/two_factor_challenge.html", email=user["email"]), 401

    _clear_login_failures(email=email, ip_address=client_ip)
    current_app.logger.info(
        "2fa_login_verify_passed user_id=%s host=%s",
        int(user["id"]),
        str(request.host or "").strip().lower(),
    )
    target = str(session.pop("post_login_next", "") or url_for("pages.dashboard"))
    flash("2FA verification complete.", "success")
    return _complete_login(user, target, show_success_flash=False)


@auth_bp.post("/2fa/recovery/send-code")
def two_factor_recovery_send_code():
    csrf_redirect = _require_csrf_or_redirect("auth.two_factor_challenge")
    if csrf_redirect:
        return csrf_redirect

    pending_id = session.get("pre_2fa_user_id")
    if pending_id is None:
        return redirect(url_for("auth.login"))

    user = _store().get_user_by_id(int(pending_id))
    if not user or not user.get("totp_enabled"):
        session.pop("pre_2fa_user_id", None)
        return redirect(url_for("auth.login"))

    settings = _settings()
    retry_after = _store().security_code_retry_after(
        purpose="twofa_reset_login",
        user_id=int(user["id"]),
        cooldown_seconds=settings.account_security_code_resend_cooldown_seconds,
    )
    if retry_after > 0:
        flash(f"Please wait {retry_after} seconds before requesting another reset code.", "info")
        return redirect(url_for("auth.two_factor_challenge"))

    code = f"{secrets.randbelow(1_000_000):06d}"
    sent = _account_mailer().send_twofa_reset_code(
        email=str(user["email"]).strip().lower(),
        code=code,
        expires_minutes=settings.account_security_code_expiry_minutes,
    )
    if not sent.get("sent"):
        flash("Unable to send 2FA reset code right now. Please retry shortly.", "error")
        return redirect(url_for("auth.two_factor_challenge"))

    _store().create_security_action_code(
        purpose="twofa_reset_login",
        user_id=int(user["id"]),
        email=str(user["email"]).strip().lower(),
        code=code,
        expiry_minutes=settings.account_security_code_expiry_minutes,
    )
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="twofa_recovery_code_sent",
    )
    flash("2FA reset code sent to your account email.", "success")
    return redirect(url_for("auth.two_factor_challenge"))


@auth_bp.post("/2fa/recovery/verify")
def two_factor_recovery_verify():
    csrf_redirect = _require_csrf_or_redirect("auth.two_factor_challenge")
    if csrf_redirect:
        return csrf_redirect

    pending_id = session.get("pre_2fa_user_id")
    if pending_id is None:
        return redirect(url_for("auth.login"))

    user = _store().get_user_by_id(int(pending_id))
    if not user or not user.get("totp_enabled"):
        session.pop("pre_2fa_user_id", None)
        return redirect(url_for("auth.login"))

    code = str(request.form.get("recovery_code", "")).strip()
    if len(code) != 6 or not code.isdigit():
        flash("Please enter a valid 6-digit recovery code.", "error")
        return redirect(url_for("auth.two_factor_challenge"))

    verification = _store().consume_security_action_code(
        purpose="twofa_reset_login",
        user_id=int(user["id"]),
        code=code,
    )
    status = str(verification.get("status", "invalid"))
    if status == "missing":
        flash("No reset code found. Request a new one.", "error")
        return redirect(url_for("auth.two_factor_challenge"))
    if status == "expired":
        flash("Reset code expired. Request a new one.", "error")
        return redirect(url_for("auth.two_factor_challenge"))
    if status != "verified":
        flash("Invalid reset code.", "error")
        return redirect(url_for("auth.two_factor_challenge"))

    _store().set_totp(int(user["id"]), secret=None, enabled=False)
    _store().bump_session_version(user_id=int(user["id"]))
    session.pop("pre_2fa_user_id", None)
    login_user(int(user["id"]))
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="twofa_reset_via_recovery",
    )
    _apply_login_anomaly_prompt(user)
    _account_mailer().send_twofa_reset_notice(email=str(user["email"]).strip().lower())
    flash("2FA has been reset. Please configure it again from Account Settings.", "success")
    return redirect(url_for("pages.account_page"))


@auth_bp.post("/logout")
def logout():
    csrf_redirect = _require_csrf_or_redirect("pages.homepage")
    if csrf_redirect:
        return csrf_redirect
    logout_user()
    response = redirect(url_for("pages.homepage"))
    _clear_session_cookie_variants(response)
    return response


@auth_bp.post("/account/change-email")
@login_required
def change_email():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    user = get_current_user()
    denied = _deny_child_self_email_change(user)
    if denied:
        return denied
    current_password = str(request.form.get("current_password", ""))
    new_email = str(request.form.get("new_email", "")).strip().lower()

    if not _is_valid_email(new_email):
        flash("Please provide a valid email address.", "error")
        return redirect(url_for("pages.account_page"))

    if not check_password_hash(user["password_hash"], current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("pages.account_page"))

    if str(user["email"]).strip().lower() == new_email:
        flash("New email must be different from your current email.", "error")
        return redirect(url_for("pages.account_page"))

    if _store().get_user_by_email(new_email):
        flash("Email is already in use.", "error")
        return redirect(url_for("pages.account_page"))

    settings = _settings()
    retry_after = _store().security_code_retry_after(
        purpose="email_change",
        user_id=int(user["id"]),
        cooldown_seconds=settings.account_security_code_resend_cooldown_seconds,
    )
    if retry_after > 0:
        flash(f"Please wait {retry_after} seconds before requesting another email-change code.", "info")
        return redirect(url_for("pages.account_page"))

    code = f"{secrets.randbelow(1_000_000):06d}"
    sent = _account_mailer().send_email_change_code(
        email=new_email,
        code=code,
        expires_minutes=settings.account_security_code_expiry_minutes,
    )
    if not sent.get("sent"):
        flash("Unable to send verification code right now. Please retry shortly.", "error")
        return redirect(url_for("pages.account_page"))

    _store().create_security_action_code(
        purpose="email_change",
        user_id=int(user["id"]),
        email=str(user["email"]).strip().lower(),
        code=code,
        expiry_minutes=settings.account_security_code_expiry_minutes,
        metadata={"new_email": new_email},
    )
    session["pending_email_change_target"] = new_email
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="email_change_code_sent",
        details={"target_email": new_email},
    )
    flash(
        f"Verification code sent to {new_email}. Enter the code below to complete email change.",
        "success",
    )
    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/change-email/confirm")
@login_required
def confirm_email_change():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    user = get_current_user()
    denied = _deny_child_self_email_change(user)
    if denied:
        return denied
    current_password = str(request.form.get("current_password", ""))
    code = str(request.form.get("code", "")).strip()

    if not check_password_hash(user["password_hash"], current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("pages.account_page"))

    step_up_redirect = _require_step_up_or_redirect(user, target_endpoint="pages.account_page")
    if step_up_redirect:
        return step_up_redirect

    if len(code) != 6 or not code.isdigit():
        flash("Please enter a valid 6-digit verification code.", "error")
        return redirect(url_for("pages.account_page"))

    verification = _store().consume_security_action_code(
        purpose="email_change",
        user_id=int(user["id"]),
        code=code,
    )
    status = str(verification.get("status", "invalid"))
    if status == "missing":
        flash("No email-change code found. Request a new code first.", "error")
        return redirect(url_for("pages.account_page"))
    if status == "expired":
        flash("Email-change code expired. Request a new code.", "error")
        return redirect(url_for("pages.account_page"))
    if status != "verified":
        flash("Invalid email-change code.", "error")
        return redirect(url_for("pages.account_page"))

    metadata = verification.get("metadata", {})
    new_email = str(metadata.get("new_email", "")).strip().lower()
    if not _is_valid_email(new_email):
        flash("Invalid target email in verification payload. Request a new code.", "error")
        return redirect(url_for("pages.account_page"))

    existing = _store().get_user_by_email(new_email)
    if existing and int(existing["id"]) != int(user["id"]):
        flash("Email is already in use.", "error")
        return redirect(url_for("pages.account_page"))

    old_email = str(user["email"]).strip().lower()
    try:
        _store().update_email(int(user["id"]), new_email)
        _store().bump_session_version(user_id=int(user["id"]))
        _record_user_operation(
            user_id=int(user["id"]),
            operation_type="email_change_confirmed",
            details={"old_email": old_email, "new_email": new_email},
        )
        session.pop("pending_email_change_target", None)
        _account_mailer().send_email_changed_notice(old_email=old_email, new_email=new_email)
        logout_user()
        flash("Email updated successfully. Please sign in again.", "success")
        return redirect(url_for("auth.login"))
    except IntegrityError:
        flash("Email is already in use.", "error")

    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/change-password")
@login_required
def change_password():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    user = get_current_user()
    current_password = str(request.form.get("current_password", ""))
    new_password = str(request.form.get("new_password", ""))
    confirm_password = str(request.form.get("confirm_password", ""))

    if not check_password_hash(user["password_hash"], current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("pages.account_page"))

    step_up_redirect = _require_step_up_or_redirect(user, target_endpoint="pages.account_page")
    if step_up_redirect:
        return step_up_redirect

    if len(new_password) < 12:
        flash("New password must be at least 12 characters.", "error")
        return redirect(url_for("pages.account_page"))

    if new_password != confirm_password:
        flash("Password confirmation does not match.", "error")
        return redirect(url_for("pages.account_page"))

    _store().update_password_hash(int(user["id"]), generate_password_hash(new_password))
    _store().bump_session_version(user_id=int(user["id"]))
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="password_change",
    )
    _account_mailer().send_password_changed_notice(email=str(user["email"]).strip().lower())
    logout_user()
    flash("Password updated. Please sign in again.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.post("/account/users/change-email-by-uid")
@login_required
@roles_required("master", "admin")
def change_user_email_by_uid():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    actor = get_current_user()
    step_up_redirect = _require_step_up_or_redirect(actor, target_endpoint="pages.account_page")
    if step_up_redirect:
        return step_up_redirect
    target_uid = str(request.form.get("target_uid", "")).strip()
    new_email = str(request.form.get("new_email", "")).strip().lower()
    if not _is_valid_email(new_email):
        flash("Please provide a valid target email.", "error")
        return redirect(url_for("pages.account_page"))

    target = _manageable_user_by_uid(actor, target_uid)
    if not target:
        flash("Target User ID is invalid or outside your management scope.", "error")
        return redirect(url_for("pages.account_page"))

    if _store().get_user_by_email(new_email):
        flash("Email is already in use.", "error")
        return redirect(url_for("pages.account_page"))

    old_email = str(target["email"]).strip().lower()
    try:
        _store().update_email(int(target["id"]), new_email)
        _store().bump_session_version(user_id=int(target["id"]))
    except IntegrityError:
        flash("Email is already in use.", "error")
        return redirect(url_for("pages.account_page"))

    _record_user_operation(
        user_id=int(actor["id"]),
        target_user_id=int(target["id"]),
        operation_type="admin_user_email_change",
        details={
            "target_uid": str(target.get("uid", "")).strip(),
            "old_email": old_email,
            "new_email": new_email,
        },
    )
    _account_mailer().send_email_changed_notice(old_email=old_email, new_email=new_email)
    flash(f"User UID {target_uid} email updated successfully.", "success")
    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/users/change-password-by-uid")
@login_required
@roles_required("master", "admin")
def change_user_password_by_uid():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    actor = get_current_user()
    step_up_redirect = _require_step_up_or_redirect(actor, target_endpoint="pages.account_page")
    if step_up_redirect:
        return step_up_redirect
    target_uid = str(request.form.get("target_uid", "")).strip()
    new_password = str(request.form.get("new_password", ""))
    confirm_password = str(request.form.get("confirm_password", ""))
    if len(new_password) < 12:
        flash("New password must be at least 12 characters.", "error")
        return redirect(url_for("pages.account_page"))
    if new_password != confirm_password:
        flash("Password confirmation does not match.", "error")
        return redirect(url_for("pages.account_page"))

    target = _manageable_user_by_uid(actor, target_uid)
    if not target:
        flash("Target User ID is invalid or outside your management scope.", "error")
        return redirect(url_for("pages.account_page"))

    _store().update_password_hash(int(target["id"]), generate_password_hash(new_password))
    _store().bump_session_version(user_id=int(target["id"]))
    _record_user_operation(
        user_id=int(actor["id"]),
        target_user_id=int(target["id"]),
        operation_type="admin_user_password_change",
        details={"target_uid": str(target.get("uid", "")).strip()},
    )
    _account_mailer().send_password_changed_notice(email=str(target["email"]).strip().lower())
    flash(f"User UID {target_uid} password updated successfully.", "success")
    return redirect(url_for("pages.account_page"))


@auth_bp.get("/account/2fa/setup")
@login_required
def setup_two_factor():
    user = get_current_user()
    if user.get("totp_enabled"):
        flash("2FA is already enabled.", "info")
        return redirect(url_for("pages.account_page"))

    secret = generate_totp_secret()
    session["pending_totp_secret"] = secret
    issuer = current_app.config["SETTINGS"].auth_2fa_issuer
    otp_uri = build_otpauth_uri(secret=secret, email=user["email"], issuer=issuer)
    return render_template(
        "auth/two_factor_setup.html",
        secret=secret,
        otp_uri=otp_uri,
        issuer=issuer,
        email=user["email"],
    )


@auth_bp.post("/account/2fa/enable")
@login_required
def enable_two_factor():
    csrf_redirect = _require_csrf_or_redirect("auth.setup_two_factor")
    if csrf_redirect:
        return csrf_redirect

    user = get_current_user()
    secret = session.get("pending_totp_secret")
    if not secret:
        flash("2FA setup session expired. Restart setup.", "error")
        return redirect(url_for("auth.setup_two_factor"))

    code = str(request.form.get("code", "")).strip()
    if not verify_totp_code(secret, code):
        flash("Invalid 2FA code.", "error")
        return redirect(url_for("auth.setup_two_factor"))

    _store().set_totp(int(user["id"]), secret=secret, enabled=True)
    session.pop("pending_totp_secret", None)
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="twofa_enabled",
    )
    flash("2FA enabled successfully.", "success")
    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/2fa/disable")
@login_required
def disable_two_factor():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    user = get_current_user()
    password = str(request.form.get("current_password", ""))
    code = str(request.form.get("code", "")).strip()

    if not user.get("totp_enabled"):
        flash("2FA is already disabled.", "info")
        return redirect(url_for("pages.account_page"))

    if not check_password_hash(user["password_hash"], password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("pages.account_page"))

    if not verify_totp_code(str(user.get("totp_secret") or ""), code):
        flash("Invalid 2FA code.", "error")
        return redirect(url_for("pages.account_page"))

    _store().set_totp(int(user["id"]), secret=None, enabled=False)
    _store().bump_session_version(user_id=int(user["id"]))
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="twofa_disabled",
    )
    logout_user()
    flash("2FA disabled. Please sign in again.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.post("/account/2fa/reset/send-code")
@login_required
def account_two_factor_reset_send_code():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    user = get_current_user()
    password = str(request.form.get("current_password", ""))
    if not check_password_hash(user["password_hash"], password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("pages.account_page"))

    if not user.get("totp_enabled"):
        flash("2FA is already disabled.", "info")
        return redirect(url_for("pages.account_page"))

    settings = _settings()
    retry_after = _store().security_code_retry_after(
        purpose="twofa_reset_account",
        user_id=int(user["id"]),
        cooldown_seconds=settings.account_security_code_resend_cooldown_seconds,
    )
    if retry_after > 0:
        flash(f"Please wait {retry_after} seconds before requesting another reset code.", "info")
        return redirect(url_for("pages.account_page"))

    code = f"{secrets.randbelow(1_000_000):06d}"
    sent = _account_mailer().send_twofa_reset_code(
        email=str(user["email"]).strip().lower(),
        code=code,
        expires_minutes=settings.account_security_code_expiry_minutes,
    )
    if not sent.get("sent"):
        flash("Unable to send 2FA reset code right now. Please retry shortly.", "error")
        return redirect(url_for("pages.account_page"))

    _store().create_security_action_code(
        purpose="twofa_reset_account",
        user_id=int(user["id"]),
        email=str(user["email"]).strip().lower(),
        code=code,
        expiry_minutes=settings.account_security_code_expiry_minutes,
    )
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="twofa_reset_code_sent",
    )
    flash("2FA reset code sent to your account email.", "success")
    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/2fa/reset/confirm")
@login_required
def account_two_factor_reset_confirm():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    user = get_current_user()
    password = str(request.form.get("current_password", ""))
    code = str(request.form.get("code", "")).strip()

    if not check_password_hash(user["password_hash"], password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("pages.account_page"))

    if len(code) != 6 or not code.isdigit():
        flash("Please enter a valid 6-digit reset code.", "error")
        return redirect(url_for("pages.account_page"))

    verification = _store().consume_security_action_code(
        purpose="twofa_reset_account",
        user_id=int(user["id"]),
        code=code,
    )
    status = str(verification.get("status", "invalid"))
    if status == "missing":
        flash("No reset code found. Request a new one.", "error")
        return redirect(url_for("pages.account_page"))
    if status == "expired":
        flash("Reset code expired. Request a new one.", "error")
        return redirect(url_for("pages.account_page"))
    if status != "verified":
        flash("Invalid reset code.", "error")
        return redirect(url_for("pages.account_page"))

    _store().set_totp(int(user["id"]), secret=None, enabled=False)
    _store().bump_session_version(user_id=int(user["id"]))
    _record_user_operation(
        user_id=int(user["id"]),
        operation_type="twofa_reset_via_account",
    )
    _account_mailer().send_twofa_reset_notice(email=str(user["email"]).strip().lower())
    logout_user()
    flash("2FA has been reset and disabled. Please sign in again.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.post("/account/users/create")
@login_required
@roles_required("master", "admin")
def create_user_account():
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    actor = get_current_user()
    step_up_redirect = _require_step_up_or_redirect(actor, target_endpoint="pages.account_page")
    if step_up_redirect:
        return step_up_redirect
    email = str(request.form.get("email", "")).strip().lower()
    first_name = _normalize_person_name(str(request.form.get("first_name", "")))
    last_name = _normalize_person_name(str(request.form.get("last_name", "")))
    password = str(request.form.get("password", ""))
    role = str(request.form.get("role", "child")).strip().lower()

    if not _is_valid_email(email):
        flash("Please provide a valid email address.", "error")
        return redirect(url_for("pages.account_page"))

    if len(first_name) > NAME_MAX_LENGTH or len(last_name) > NAME_MAX_LENGTH:
        flash(f"Name and surname must be at most {NAME_MAX_LENGTH} characters.", "error")
        return redirect(url_for("pages.account_page"))

    if len(password) < 12:
        flash("Account password must be at least 12 characters.", "error")
        return redirect(url_for("pages.account_page"))

    if actor["role"] == "admin":
        role = "child"

    if actor["role"] == "master" and role not in {"admin", "child"}:
        flash("Master can create admin or child accounts only.", "error")
        return redirect(url_for("pages.account_page"))

    parent_user_id = actor["id"] if role == "child" else None
    if role == "child" and actor["role"] == "master":
        parent_raw = str(request.form.get("parent_user_id", "")).strip()
        if parent_raw:
            try:
                parent_user_id = int(parent_raw)
            except ValueError:
                parent_user_id = None

    try:
        created_user_id = _store().create_user(
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            parent_user_id=parent_user_id,
            created_by_user_id=int(actor["id"]),
            first_name=first_name,
            last_name=last_name,
        )
        _apply_special_account_entitlements(int(created_user_id), email)
        created_user = _store().get_user_by_id(int(created_user_id))
        _record_user_operation(
            user_id=int(actor["id"]),
            target_user_id=int(created_user_id),
            operation_type="admin_user_create",
            details={
                "target_uid": str((created_user or {}).get("uid", "")).strip(),
                "target_email": email,
                "target_role": role,
            },
        )
        flash("Account created.", "success")
    except IntegrityError:
        flash("Email already exists.", "error")
    except ValueError as exc:
        flash(str(exc), "error")

    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/users/<int:user_id>/set-active")
@login_required
@roles_required("master", "admin")
def set_user_active(user_id: int):
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    actor = get_current_user()
    step_up_redirect = _require_step_up_or_redirect(actor, target_endpoint="pages.account_page")
    if step_up_redirect:
        return step_up_redirect
    target = _store().get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("pages.account_page"))

    active_raw = str(request.form.get("is_active", "1")).strip().lower()
    desired_active = active_raw in {"1", "true", "yes", "on"}

    if actor["role"] == "admin":
        if target.get("role") != "child" or int(target.get("parent_user_id") or 0) != int(actor["id"]):
            flash("Admins can only manage their child accounts.", "error")
            return redirect(url_for("pages.account_page"))

    if actor["role"] == "master" and target.get("role") == "master":
        flash("Master account cannot be deactivated here.", "error")
        return redirect(url_for("pages.account_page"))

    _store().set_active(user_id, desired_active)
    _store().bump_session_version(user_id=int(user_id))
    _record_user_operation(
        user_id=int(actor["id"]),
        target_user_id=int(user_id),
        operation_type="admin_user_set_active",
        details={"is_active": bool(desired_active), "target_uid": str(target.get("uid", "")).strip()},
    )
    flash("Account status updated.", "success")
    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/users/<int:user_id>/delete")
@login_required
@roles_required("master", "admin")
def delete_user_account(user_id: int):
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    actor = get_current_user()
    required_2fa_redirect = _require_totp_code_or_redirect(
        actor,
        target_endpoint="pages.account_page",
        code_field="delete_2fa_code",
        operation_name="admin_user_delete",
    )
    if required_2fa_redirect:
        return required_2fa_redirect

    target = _store().get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("pages.account_page"))

    if int(actor["id"]) == int(target["id"]):
        flash("You cannot delete your own account from this panel.", "error")
        return redirect(url_for("pages.account_page"))

    target_role = str(target.get("role", "")).strip().lower()
    target_email = str(target.get("email", "")).strip().lower()
    allow_placeholder_master_delete = target_role == "master" and _is_placeholder_master_email(target_email)
    if target_role == "master" and not allow_placeholder_master_delete:
        flash("Master account deletion is blocked from this panel.", "error")
        return redirect(url_for("pages.account_page"))

    if actor["role"] == "admin":
        if target_role != "child" or int(target.get("parent_user_id") or 0) != int(actor["id"]):
            flash("Admins can only delete their own child accounts.", "error")
            return redirect(url_for("pages.account_page"))

    child_count = _store().count_children(parent_user_id=int(user_id))
    if child_count > 0:
        flash("Cannot delete this account while it still has child accounts assigned.", "error")
        return redirect(url_for("pages.account_page"))

    deleted = _store().delete_user(user_id=int(user_id))
    if not deleted:
        flash("User not found.", "error")
        return redirect(url_for("pages.account_page"))

    _record_user_operation(
        user_id=int(actor["id"]),
        target_user_id=int(user_id),
        operation_type="admin_user_delete",
        details={
            "target_uid": str(target.get("uid", "")).strip(),
            "target_email": target_email,
            "target_role": target_role,
        },
    )
    flash("Account deleted permanently.", "success")
    return redirect(url_for("pages.account_page"))


@auth_bp.post("/account/users/<int:user_id>/set-role")
@login_required
@roles_required("master")
def set_user_role(user_id: int):
    csrf_redirect = _require_csrf_or_redirect("pages.account_page")
    if csrf_redirect:
        return csrf_redirect

    actor = get_current_user()
    step_up_redirect = _require_step_up_or_redirect(actor, target_endpoint="pages.account_page")
    if step_up_redirect:
        return step_up_redirect
    target = _store().get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("pages.account_page"))

    if int(actor["id"]) == int(target["id"]):
        flash("Cannot change your own role.", "error")
        return redirect(url_for("pages.account_page"))

    if target.get("role") == "master":
        flash("Master role cannot be changed here.", "error")
        return redirect(url_for("pages.account_page"))

    new_role = str(request.form.get("role", "")).strip().lower()
    if new_role not in {"admin", "child"}:
        flash("Role must be admin or child.", "error")
        return redirect(url_for("pages.account_page"))

    _store().set_role(user_id, new_role)
    _store().bump_session_version(user_id=int(user_id))
    if new_role == "admin":
        _store().set_parent(user_id, None)
    _record_user_operation(
        user_id=int(actor["id"]),
        target_user_id=int(user_id),
        operation_type="admin_user_set_role",
        details={"role": new_role, "target_uid": str(target.get("uid", "")).strip()},
    )
    flash("Role updated.", "success")
    return redirect(url_for("pages.account_page"))
