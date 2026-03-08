"""Session auth helpers and route guards."""

from __future__ import annotations

from functools import wraps
import secrets
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode, urlparse

from flask import current_app, g, jsonify, redirect, request, session, url_for


def _store():
    return current_app.config["USER_STORE"]


def get_current_user() -> Optional[Dict[str, Any]]:
    if hasattr(g, "current_user"):
        return g.current_user

    user_id = session.get("user_id")
    if user_id is None:
        g.current_user = None
        return None

    try:
        user = _store().get_user_by_id(int(user_id))
    except Exception:
        user = None

    if not user or not user.get("is_active", False):
        session.pop("user_id", None)
        session.pop("session_auth_version", None)
        g.current_user = None
        return None

    session_version = int(session.get("session_auth_version") or 0)
    current_session_version = max(1, int(user.get("session_version") or 1))
    if session_version and session_version != current_session_version:
        session.pop("user_id", None)
        session.pop("session_auth_version", None)
        session["session_security_notice"] = "Session expired due to account security changes. Please sign in again."
        g.current_user = None
        return None
    if not session_version:
        session["session_auth_version"] = current_session_version

    g.current_user = user
    return user


def load_current_user() -> None:
    get_current_user()


def login_user(user_id: int) -> None:
    session.pop("pre_2fa_user_id", None)
    session.permanent = True
    normalized_user_id = int(user_id)
    session["user_id"] = normalized_user_id
    try:
        user = _store().get_user_by_id(normalized_user_id)
        session["session_auth_version"] = max(1, int((user or {}).get("session_version") or 1))
    except Exception:
        session["session_auth_version"] = 1


def logout_user() -> None:
    keep_csrf = session.get("_csrf_token")
    security_notice = session.get("session_security_notice")
    session.clear()
    if keep_csrf:
        session["_csrf_token"] = keep_csrf
    if security_notice:
        session["session_security_notice"] = security_notice


def get_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["_csrf_token"] = token
    return token


def validate_csrf_token(submitted: Optional[str]) -> bool:
    expected = session.get("_csrf_token")
    if not expected or not submitted:
        return False
    return secrets.compare_digest(str(expected), str(submitted))


def _safe_next_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    if not value.startswith("/"):
        return None
    if value.startswith("//"):
        return None
    return value


def redirect_to_login() -> Any:
    next_target = request.full_path if request.query_string else request.path
    query = urlencode({"next": next_target})
    return redirect(f"{url_for('auth.login')}?{query}")


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return redirect_to_login()
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles: str) -> Callable:
    accepted = {str(role).strip().lower() for role in roles}

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect_to_login()
            if str(user.get("role", "")).lower() not in accepted:
                return redirect(url_for("pages.dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def api_login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)

    return wrapped


def api_roles_required(*roles: str) -> Callable:
    accepted = {str(role).strip().lower() for role in roles}

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "unauthorized"}), 401
            if str(user.get("role", "")).lower() not in accepted:
                return jsonify({"error": "forbidden"}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def pull_safe_next(default_endpoint: str = "pages.dashboard") -> str:
    supplied = request.values.get("next")
    safe = _safe_next_url(supplied)
    if safe:
        return safe
    return url_for(default_endpoint)
