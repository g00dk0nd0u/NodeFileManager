#!/bin/sh
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(dirname -- "$SCRIPT_DIR")
cd "$REPOSITORY_ROOT" || exit 1

echo "NodeFileManager launcher"
echo "Repository: $REPOSITORY_ROOT"
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: A compatible python3 was not found." >&2
  echo "Install Python 3, then double-click this launcher again." >&2
  exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "ERROR: Python 3.10 or newer is required." >&2
  exit 1
fi
echo "The browser will open after the health check passes. Press Ctrl+C to stop."
exec python3 -m backend.launcher
