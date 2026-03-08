"""HTTP security headers for the portal scaffold."""

from flask import Response

from .config import Settings


def apply_security_headers(response: Response, settings: Settings) -> Response:
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "media-src 'self' https:; "
        "script-src 'self' https://challenges.cloudflare.com https://widget.trustpilot.com; "
        "frame-src 'self' https://challenges.cloudflare.com https://nowpayments.io https://*.nowpayments.io https://widget.trustpilot.com https://*.trustpilot.com; "
        "connect-src 'self' https://challenges.cloudflare.com https://widget.trustpilot.com https://*.trustpilot.com; "
        "style-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    if settings.force_https:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response
