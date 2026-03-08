#!/usr/bin/env python3
"""Build sanitized public docs from private docs/Website markdown."""

from __future__ import annotations

from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "docs" / "Website"
TARGET_DIR = ROOT / "docs" / "Website_public"

ALLOWED_MD_FILES = [
    "index.md",
    "architecture.md",
    "data-fetching-and-caching.md",
    "scoring-model.md",
    "eu-mode-and-global-mode.md",
    "social-score.md",
    "token-data-viewer.md",
    "dashboard-and-outputs.md",
    "running-and-configuration.md",
    "secure-credentials.md",
]

PATH_RE = re.compile(r"(?<!\w)/(Users|opt|home|etc|var|srv|root|tmp)/[^\s`\"')]+")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SECRET_ASSIGN_RE = re.compile(
    r"(?im)\b([A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*)\s*=\s*([^\s#]+)"
)
CREDENTIAL_INLINE_RE = re.compile(
    r"(?im)\b(api[_ -]?key|secret|token|password)\b\s*[:=]\s*([^\s`\"')]+)"
)


def sanitize_markdown(text: str) -> str:
    out = text
    out = out.replace("DeFi Complete Risk Assessment Suite", "Hodler Suite")
    out = out.replace("DeFi Risk Assessment Suite", "Hodler Suite")
    out = out.replace("DeFi Risk Assessment", "Hodler Suite")
    out = out.replace("DeFi Risk Suite", "Hodler Suite")
    out = PATH_RE.sub("<REDACTED_PATH>", out)
    out = IPV4_RE.sub("<REDACTED_IP>", out)
    out = SECRET_ASSIGN_RE.sub(r"\1=<REDACTED>", out)
    out = CREDENTIAL_INLINE_RE.sub(r"\1: <REDACTED>", out)
    return out


def build() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Remove stale content while keeping directory.
    for item in TARGET_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    banner = (
        "> **Public security notice:** This documentation is intentionally redacted. "
        "Sensitive server paths, private keys, secret tokens, and origin network details are removed.\n\n"
    )

    for rel in ALLOWED_MD_FILES:
        src = SOURCE_DIR / rel
        if not src.is_file():
            continue
        body = src.read_text(encoding="utf-8", errors="replace")
        clean = banner + sanitize_markdown(body)
        (TARGET_DIR / rel).write_text(clean, encoding="utf-8")

    # Do not emit README.md in docs_dir because MkDocs can warn if index.md is present.


if __name__ == "__main__":
    build()
    print(f"Public docs generated at: {TARGET_DIR}")
