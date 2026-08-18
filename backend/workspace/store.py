"""Small atomic JSON store for workspace layout (never user file contents)."""

from __future__ import annotations

import json
import uuid
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
            data = {}
        return self._migrate(data if isinstance(data, dict) else {})

    @staticmethod
    def _migrate(data: dict[str, object]) -> dict[str, object]:
        """Normalize legacy tree state into explicit folder/panel/set identities."""
        nodes = data.get("nodes") if isinstance(data.get("nodes"), dict) else {}
        sets = data.get("workingSets") if isinstance(data.get("workingSets"), dict) else {}
        migrated_nodes: dict[str, object] = {}
        default_set = next(iter(sets), f"working-set-{uuid.uuid4().hex[:12]}")
        for legacy_id, value in nodes.items():
            if not isinstance(value, dict):
                continue
            node = dict(value)
            node.setdefault("folderId", legacy_id)
            node.setdefault("panelInstanceId", legacy_id)
            node.setdefault("workingSetId", default_set)
            node.setdefault("visualParentPanelId", node.pop("parentId", None))
            node.setdefault("fsParentFolderId", None)
            migrated_nodes[str(node["panelInstanceId"])] = node
        if migrated_nodes and not sets:
            sets = {default_set: {"workingSetId": default_set, "name": "Working Set"}}
        return {
            **data,
            "version": 2,
            "roots": data.get("roots", []) if isinstance(data.get("roots"), list) else [],
            "nodes": migrated_nodes,
            "workingSets": sets,
            "viewport": data.get("viewport") if isinstance(data.get("viewport"), dict) else {"x": 0, "y": 0, "zoom": 1},
        }

    def save(self, state: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
