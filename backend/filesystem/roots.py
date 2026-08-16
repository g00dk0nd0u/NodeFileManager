"""Session-scoped authorization for user-selected directory roots."""

from __future__ import annotations

import hashlib
from pathlib import Path
from threading import RLock


def folder_id(path: Path) -> str:
    canonical = str(path.resolve()).casefold()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class RootRegistry:
    def __init__(self) -> None:
        self._roots: set[Path] = set()
        self._folders: dict[str, Path] = {}
        self._lock = RLock()

    def authorize_root(self, path: str | Path) -> Path:
        candidate = Path(path).resolve(strict=True)
        if not candidate.is_dir():
            raise NotADirectoryError(candidate)
        with self._lock:
            self._roots.add(candidate)
            self._folders[folder_id(candidate)] = candidate
        return candidate

    def remember(self, path: Path) -> str:
        resolved = path.resolve(strict=True)
        with self._lock:
            if not any(resolved == root or root in resolved.parents for root in self._roots):
                raise PermissionError("Folder is outside the selected roots")
            identifier = folder_id(resolved)
            self._folders[identifier] = resolved
            return identifier

    def get(self, identifier: str) -> Path:
        with self._lock:
            path = self._folders.get(identifier)
            if path is None or not any(path == root or root in path.parents for root in self._roots):
                raise PermissionError("Folder is not authorized")
            return path
