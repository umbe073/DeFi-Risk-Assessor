"""Runtime paths stub for local development."""

import os
from pathlib import Path


def resolve_api_runtime_dir() -> Path:
    """Resolve the API runtime directory."""
    default = Path(__file__).resolve().parents[1] / "data" / "runtime"
    runtime_dir = Path(os.getenv("RISK_API_RUNTIME_DIR", str(default)))
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir
