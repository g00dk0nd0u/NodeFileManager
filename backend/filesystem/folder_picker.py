"""Supervised subprocess boundary for native folder selection."""

from __future__ import annotations

import json
import subprocess
import sys

PICKER_TIMEOUT_SECONDS = 10 * 60


class FolderPickerUnavailable(RuntimeError):
    """Raised when the isolated picker cannot return a valid result."""


def _creation_flags() -> int:
    """Avoid an extra console window for the short-lived child on Windows."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def select_folder() -> str | None:
    """Run the native chooser in a child; cancellation returns ``None``."""
    command = [sys.executable, "-m", "backend.filesystem.folder_picker_child"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PICKER_TIMEOUT_SECONDS,
            check=False,
            creationflags=_creation_flags(),
        )
    except subprocess.TimeoutExpired as error:
        # subprocess.run kills and waits for the child before raising.
        raise FolderPickerUnavailable(
            "フォルダー選択がタイムアウトしました。もう一度お試しください。"
        ) from error
    except OSError as error:
        raise FolderPickerUnavailable(
            f"フォルダー選択プロセスを開始できませんでした: {error}"
        ) from error

    if completed.returncode != 0:
        detail = completed.stderr.strip()
        suffix = f" ({detail})" if detail else ""
        raise FolderPickerUnavailable(
            f"フォルダー選択プロセスが異常終了しました{suffix}"
        )
    try:
        result = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise FolderPickerUnavailable(
            "フォルダー選択プロセスから不正な応答が返されました。"
        ) from error
    if not isinstance(result, dict) or result.get("status") not in {
        "selected", "cancelled", "error"
    }:
        raise FolderPickerUnavailable(
            "フォルダー選択プロセスから不正な応答が返されました。"
        )
    if result["status"] == "cancelled":
        return None
    if result["status"] == "error":
        reason = result.get("reason")
        if not isinstance(reason, str) or not reason:
            reason = "詳細不明のエラー"
        raise FolderPickerUnavailable(f"フォルダー選択に失敗しました: {reason}")
    path = result.get("path")
    if not isinstance(path, str) or not path:
        raise FolderPickerUnavailable(
            "フォルダー選択プロセスから不正な応答が返されました。"
        )
    return path
