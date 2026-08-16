"""Small atomic JSON store for workspace layout (never user file contents)."""

from __future__ import annotations

import json
from pathlib import Path

from backend.runtime_paths import user_data_directory


def default_workspace_path() -> Path:
    return user_data_directory() / "workspace.json"


class WorkspaceStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_workspace_path()

    def load(self) -> dict[str, object]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"version": 1, "roots": [], "nodes": {}, "viewport": {"x": 0, "y": 0, "zoom": 1}}
        return data if isinstance(data, dict) else {"version": 1, "roots": [], "nodes": {}, "viewport": {"x": 0, "y": 0, "zoom": 1}}

    def save(self, state: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
