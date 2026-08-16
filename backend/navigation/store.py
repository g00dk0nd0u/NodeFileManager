"""Thread-safe, bounded and atomic quick-access JSON persistence."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from backend.runtime_paths import user_data_directory

MAX_FAVORITES = 100
MAX_USAGE = 256


def default_quick_access_path() -> Path:
    return user_data_directory() / "quick_access.json"


class QuickAccessStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_quick_access_path()
        self._lock = threading.RLock()

    @staticmethod
    def empty() -> dict[str, object]:
        return {"version": 1, "favorites": [], "usage": {}}

    def load(self) -> dict[str, object]:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                return self.empty()
            if not isinstance(raw, dict):
                return self.empty()
            favorites = [item for item in raw.get("favorites", []) if isinstance(item, dict)
                         and isinstance(item.get("id"), str) and isinstance(item.get("path"), str)][:MAX_FAVORITES]
            usage = raw.get("usage", {})
            if not isinstance(usage, dict):
                usage = {}
            valid_usage = {key: value for key, value in usage.items() if isinstance(key, str)
                           and isinstance(value, dict) and isinstance(value.get("path"), str)
                           and isinstance(value.get("count"), int) and value["count"] > 0
                           and isinstance(value.get("lastUsed"), (int, float))}
            newest = sorted(valid_usage.items(), key=lambda item: item[1]["lastUsed"], reverse=True)[:MAX_USAGE]
            return {"version": 1, "favorites": favorites, "usage": dict(newest)}

    def update(self, mutate):
        with self._lock:
            state = self.load()
            result = mutate(state)
            self._save_locked(state)
            return result

    def _save_locked(self, state: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(state, output, ensure_ascii=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            try: temporary.unlink()
            except FileNotFoundError: pass
