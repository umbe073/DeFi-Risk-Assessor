"""Health endpoints."""

from flask import Blueprint, jsonify


health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})
