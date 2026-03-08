#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/bin/zensical" ]]; then
  "$ROOT_DIR/bin/zensical" serve -f mkdocs.yml -a 127.0.0.1:8000 "$@"
  exit 0
fi

if command -v zensical >/dev/null 2>&1; then
  zensical serve -f mkdocs.yml -a 127.0.0.1:8000 "$@"
  exit 0
fi

echo "zensical is not installed. Install with:" >&2
echo "  ./bin/python -m pip install 'zensical>=0.0.23'" >&2
exit 1
