"""Constrained filesystem mutations for explicitly authorized items."""

from __future__ import annotations

import shutil
from pathlib import Path

from .directory_service import DirectoryService
from .roots import RootRegistry


class FileOperationError(ValueError):
    pass


class FileOperations:
    def __init__(self, roots: RootRegistry, directories: DirectoryService) -> None:
        self.roots, self.directories = roots, directories

    @staticmethod
    def _validate_name(name: object) -> str:
        if not isinstance(name, str) or not name.strip():
            raise FileOperationError("Name must not be empty")
        if name in {".", ".."} or "/" in name or "\\" in name:
            raise FileOperationError("Name must not contain path separators")
        return name

    @staticmethod
    def _ensure_available(target: Path) -> None:
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Destination already exists: {target.name}")

    @staticmethod
    def _reject_recursive(source: Path, destination: Path) -> None:
        if source.is_dir() and (destination == source or source in destination.parents):
            raise FileOperationError("A folder cannot be copied or moved into itself")

    def rename(self, identifier: str, name: object) -> dict[str, object]:
        source = self.roots.path_for(identifier)
        was_root = self.roots.is_root(source)
        target = source.with_name(self._validate_name(name))
        self._ensure_available(target)
        source.rename(target)
        self.roots.replace(source, target)
        parent_id = None if was_root else self.roots.remember(target.parent)
        return self.directories.metadata(target, parent_id)

    def copy(self, identifier: str, destination_id: str) -> dict[str, object]:
        source, destination = self.roots.path_for(identifier), self.roots.get(destination_id)
        target = destination / source.name
        self._reject_recursive(source, destination)
        self._ensure_available(target)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        return self.directories.metadata(target, destination_id)

    def move(self, identifier: str, destination_id: str) -> dict[str, object]:
        source, destination = self.roots.path_for(identifier), self.roots.get(destination_id)
        if self.roots.is_root(source):
            raise FileOperationError("A selected root cannot be moved; move its contents instead")
        target = destination / source.name
        if source.parent == destination:
            raise FileOperationError("Item is already in that folder")
        self._reject_recursive(source, destination)
        self._ensure_available(target)
        shutil.move(str(source), str(target))
        self.roots.replace(source, target)
        return self.directories.metadata(target, destination_id)
