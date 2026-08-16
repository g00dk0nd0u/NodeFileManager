"""Application and build identity (safe to expose through localhost health)."""

from __future__ import annotations

import os

from backend.build_info import BUILD_COMMIT as EMBEDDED_BUILD_COMMIT

VERSION = "0.3.5"
BUILD_COMMIT = os.environ.get("NODEFILEMANAGER_BUILD_COMMIT", "").strip() or EMBEDDED_BUILD_COMMIT
