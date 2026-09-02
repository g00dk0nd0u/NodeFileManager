"""Lazy immediate-directory metadata exposed to the frontend."""

import os
import time
from pathlib import Path
from threading import RLock

from .roots import RootRegistry


class DirectoryService:
    def __init__(self, roots: RootRegistry) -> None:
        self.roots = roots
        self._hidden_paths: set[Path] = set()
        self._hidden_lock = RLock()

    def hide_internal(self, path: Path) -> None:
        """Keep a server-owned mutation path out of all API listings."""
        with self._hidden_lock:
            self._hidden_paths.add(path.absolute())

    def reveal_internal(self, path: Path) -> None:
        with self._hidden_lock:
            self._hidden_paths.discard(path.absolute())

    def _is_hidden(self, path: Path) -> bool:
        absolute = path.absolute()
        with self._hidden_lock:
            return any(hidden == absolute or hidden in absolute.parents for hidden in self._hidden_paths)

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
            if self._is_hidden(path):
                continue
            kind = "folder" if is_folder else "file"
            try:
                modified_time = None if is_folder else entry.stat(follow_symlinks=False).st_mtime
            except OSError:
                modified_time = None
            item = {
                "id": self.roots.remember_child(parent, entry.name),
                "name": entry.name,
                "path": str(path),
                "parentId": parent_id,
                "kind": kind,
                "extension": "" if is_folder else path.suffix,
                "childrenState": "unknown" if is_folder else "empty",
                "hasChildren": is_folder,
                "modifiedTime": modified_time,
            }
            (folders if is_folder else files).append(item)
        return {"folders": folders, "files": files}

    def children(self, parent_id: str) -> list[dict[str, object]]:
        return self.contents(parent_id)["folders"]

    def parent(self, folder_id: str) -> dict[str, object] | None:
        folder = self.roots.get(folder_id)
        parent = folder.parent
        if parent == folder:
            return None
        # The requested folder was already server-authorized. Resolve and register
        # exactly one real parent; never accept a client-provided path here.
        return self.metadata(self.roots.authorize_root(str(parent)))

    def search(
        self,
        folder_id: str,
        query: str,
        limit: int = 100,
        max_entries: int = 10_000,
        time_budget: float = 1.5,
    ) -> dict[str, object]:
        term = query.strip().casefold()
        if len(term) < 2:
            raise ValueError("Search requires at least two characters")
        root = self.roots.get(folder_id)
        results: list[dict[str, object]] = []
        visited = 0
        deadline = time.monotonic() + time_budget
        pending = [root]
        while pending:
            current = pending.pop()
            parent = self.metadata(current)
            try:
                entries = os.scandir(current)
            except OSError:
                continue
            with entries:
                for entry in entries:
                    visited += 1
                    if visited > max_entries or time.monotonic() >= deadline:
                        return {"results": results, "truncated": True}
                    if entry.is_symlink():
                        continue
                    is_folder = entry.is_dir(follow_symlinks=False)
                    path = current / entry.name
                    if self._is_hidden(path):
                        continue
                    if is_folder:
                        pending.append(path)
                    if term not in entry.name.casefold():
                        continue
                    item = self.metadata(path, str(parent["id"]))
                    item["parentFolder"] = parent
                    results.append(item)
                    if len(results) >= limit:
                        return {"results": results, "truncated": True}
        return {"results": results, "truncated": False}
