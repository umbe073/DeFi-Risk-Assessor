#!/usr/bin/env python3
"""Probe CoinGlass Open API v4 with CG-API-KEY (env COINGLASS_API_KEY).

Docs: https://docs.coinglass.com/reference/authentication
Base: https://open-api-v4.coinglass.com

There is no keyless public tier: requests without a valid key get code 401 in the JSON body.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


BASE = "https://open-api-v4.coinglass.com"


def _get_json(url: str, api_key: str) -> tuple[int, dict[str, str], Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "CG-API-KEY": api_key,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = int(resp.status)
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        hdrs = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        body = exc.read().decode("utf-8", errors="replace")
    try:
        payload: Any = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        payload = {"_raw": body[:2000]}
    return status, hdrs, payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default="/api/futures/supported-coins",
        help="API path under base URL (default: supported futures coins).",
    )
    args = parser.parse_args()

    key = str(os.environ.get("COINGLASS_API_KEY", "")).strip()
    if not key:
        print("Set COINGLASS_API_KEY in the environment, then re-run.", file=sys.stderr)
        print("Example: COINGLASS_API_KEY='...' python3 scripts/v2.0/tools/coinglass_api_probe.py", file=sys.stderr)
        return 2

    path = str(args.path).strip()
    if not path.startswith("/"):
        path = "/" + path
    url = f"{BASE}{path}"

    status, hdrs, payload = _get_json(url, key)
    print(f"URL: {url}")
    print(f"HTTP status: {status}")
    for h in ("api-key-max-limit", "api-key-use-limit"):
        if h in hdrs:
            print(f"Header {h}: {hdrs[h]}")

    if isinstance(payload, dict):
        code = payload.get("code")
        msg = payload.get("msg")
        if code is not None:
            print(f"Body code: {code} msg: {msg}")
        data = payload.get("data")
        if data is not None:
            if isinstance(data, list):
                print(f"data: list len={len(data)}")
                for i, row in enumerate(data[:15]):
                    print(f"  [{i}] {row}")
                if len(data) > 15:
                    print(f"  ... ({len(data) - 15} more)")
            else:
                snippet = json.dumps(data, indent=2)[:4000]
                print(f"data (snippet):\n{snippet}")
        else:
            print(json.dumps(payload, indent=2)[:4000])
    else:
        print(json.dumps(payload, indent=2)[:4000])

    # CoinGlass often uses body "code" string "0" for success
    if isinstance(payload, dict) and str(payload.get("code")) == "0":
        return 0
    if status == 200 and isinstance(payload, dict) and payload.get("data") is not None:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
