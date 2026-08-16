"""Session-scoped authorization for user-selected directory roots."""

from __future__ import annotations

import hashlib
from pathlib import Path
from threading import RLock


def folder_id(path: Path) -> str:
    canonical = str(path.resolve()).casefold()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


item_id = folder_id


def lexical_item_id(path: Path) -> str:
    return hashlib.sha256(str(path.absolute()).casefold().encode("utf-8")).hexdigest()[:24]


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

    def remember_child(self, parent: Path, name: str) -> str:
        """Register an immediate lexical child without resolving it on the listing path."""
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError("Invalid child name")
        child = parent / name
        identifier = lexical_item_id(child)
        with self._lock:
            if parent not in self._roots and not any(root in parent.parents for root in self._roots):
                raise PermissionError("Parent folder is outside the selected roots")
            self._folders[identifier] = child
        return identifier

    def path_for(self, identifier: str) -> Path:
        """Return an existing authorized item, rejecting stale IDs and symlink escapes."""
        with self._lock:
            path = self._folders.get(identifier)
            roots = tuple(self._roots)
        if path is None:
            raise PermissionError("Item is not authorized")
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise FileNotFoundError("Item no longer exists") from error
        if not any(resolved == root or root in resolved.parents for root in roots):
            raise PermissionError("Item is outside the selected roots")
        return resolved

    def get(self, identifier: str) -> Path:
        path = self.path_for(identifier)
        if not path.is_dir():
            raise NotADirectoryError("Authorized item is not a folder")
        return path

    def is_root(self, path: Path) -> bool:
        resolved = path.resolve(strict=True)
        with self._lock:
            return resolved in self._roots

    def replace(self, old_path: Path, new_path: Path) -> None:
        """Keep authorization useful after an in-root rename or move."""
        old_path, new_path = old_path.resolve(), new_path.resolve()
        with self._lock:
            self._roots = {new_path if root == old_path else root for root in self._roots}
            replacements = {}
            for path in self._folders.values():
                if path == old_path or old_path in path.parents:
                    replacements[item_id(new_path / path.relative_to(old_path))] = new_path / path.relative_to(old_path)
                else:
                    replacements[item_id(path)] = path
            self._folders = replacements
