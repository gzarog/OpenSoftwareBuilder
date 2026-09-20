#!/usr/bin/env bash
# OSB one-time registration / doctor / upgrade launcher for Linux, macOS, and WSL.
#
# This script only resolves its own location and hands off to the cross-platform Python
# implementation at osb/scripts/install.py — it contains no workflow policy itself and
# starts no background process. Requires Python 3.11+.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd -P)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "osb/install.sh: python3 (3.11+) was not found on PATH" >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/scripts/install.py" "$@"
