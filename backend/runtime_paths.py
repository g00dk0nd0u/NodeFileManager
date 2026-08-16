"""Centralized source and frozen-application resource/storage paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "NodeFileManager"


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_directory() -> Path:
    if is_packaged():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parent.parent


def frontend_directory() -> Path:
    return resource_directory() / "frontend"


def user_data_directory() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / APP_NAME
    # Preserve the location used by earlier source releases on macOS and Unix.
    return Path.home() / ".nodefilemanager"


def log_directory() -> Path:
    return user_data_directory() / "logs"
