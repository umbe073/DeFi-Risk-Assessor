"""Token list CSV parser stub for local development."""

from typing import Any, Dict, List, Tuple


def parse_desktop_tokens_csv(raw: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parse a CSV of tokens for batch assessment.

    Returns (entries, errors).
    """
    entries: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return [], ["Failed to decode CSV content."]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return [], ["CSV file is empty."]

    for i, line in enumerate(lines[1:], start=2):
        parts = line.split(",")
        if len(parts) < 1:
            errors.append(f"Row {i}: empty row")
            continue
        address = parts[0].strip()
        chain = parts[1].strip() if len(parts) > 1 else ""
        if address:
            entries.append({"token_address": address, "token_chain": chain})

    return entries, errors
