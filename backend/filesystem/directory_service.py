"""Lazy immediate-directory metadata exposed to the frontend."""

import os
from pathlib import Path

from .roots import RootRegistry


class DirectoryService:
    def __init__(self, roots: RootRegistry) -> None:
        self.roots = roots

    def metadata(self, path: Path, parent_id: str | None = None) -> dict[str, object]:
        identifier = self.roots.remember(path)
        kind = "folder" if path.is_dir() else "file"
        return {
            "id": identifier,
            "name": path.name or str(path),
            "path": str(path),
            "parentId": parent_id,
            "kind": kind,
            "extension": path.suffix if kind == "file" else "",
            "childrenState": "unknown" if kind == "folder" else "empty",
            "hasChildren": kind == "folder",
        }

    def select(self, path: str) -> dict[str, object]:
        return self.metadata(self.roots.authorize_root(path))

    def contents(self, parent_id: str) -> dict[str, list[dict[str, object]]]:
        parent = self.roots.get(parent_id)
        folders, files = [], []
        try:
            with os.scandir(parent) as scan:
                entries = [(entry, entry.is_dir(follow_symlinks=False)) for entry in scan]
            entries.sort(key=lambda item: (not item[1], item[0].name.casefold()))
        except OSError as error:
            raise PermissionError(f"Folder cannot be read: {error}") from error
        for entry, is_folder in entries:
            path = parent / entry.name
            kind = "folder" if is_folder else "file"
            item = {
                "id": self.roots.remember_child(parent, entry.name),
                "name": entry.name,
                "path": str(path),
                "parentId": parent_id,
                "kind": kind,
                "extension": "" if is_folder else path.suffix,
                "childrenState": "unknown" if is_folder else "empty",
                "hasChildren": is_folder,
            }
            (folders if is_folder else files).append(item)
        return {"folders": folders, "files": files}

    def children(self, parent_id: str) -> list[dict[str, object]]:
        return self.contents(parent_id)["folders"]
