"""Constrained filesystem mutations for explicitly authorized items."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import threading
import uuid
from pathlib import Path

from .directory_service import DirectoryService
from .roots import RootRegistry


class FileOperationError(ValueError):
    pass


class FileOperationConflict(FileOperationError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class FileOperations:
    def __init__(self, roots: RootRegistry, directories: DirectoryService, on_path_moved=None) -> None:
        self.roots, self.directories = roots, directories
        self.on_path_moved = on_path_moved or (lambda old, new: None)
        self._receipts: dict[str, dict[str, object]] = {}
        self._receipt_lock = threading.Lock()

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

    @staticmethod
    def _is_filesystem_link(path: Path) -> bool:
        is_junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(is_junction and is_junction())

    @classmethod
    def _reject_linked_tree(cls, source: Path) -> None:
        """Preflight without following symlinks or Windows directory junctions."""
        with os.scandir(source) as entries:
            for entry in entries:
                path = Path(entry.path)
                if cls._is_filesystem_link(path):
                    raise FileOperationError(
                        f"Folder copy cannot include filesystem links: {path.name}"
                    )
                if entry.is_dir(follow_symlinks=False):
                    cls._reject_linked_tree(path)

    @classmethod
    def _copy_tree(cls, source: Path, target: Path) -> None:
        """Copy an already-checked tree while rechecking links during traversal."""
        if cls._is_filesystem_link(source):
            raise FileOperationError(
                f"Folder copy cannot include filesystem links: {source.name}"
            )
        target.mkdir()
        with os.scandir(source) as entries:
            for entry in entries:
                source_entry = Path(entry.path)
                if cls._is_filesystem_link(source_entry):
                    raise FileOperationError(
                        f"Folder copy cannot include filesystem links: {source_entry.name}"
                    )
                target_entry = target / entry.name
                if entry.is_dir(follow_symlinks=False):
                    cls._copy_tree(source_entry, target_entry)
                else:
                    shutil.copy2(source_entry, target_entry, follow_symlinks=False)
        shutil.copystat(source, target)

    def rename(self, identifier: str, name: object) -> dict[str, object]:
        source = self.roots.path_for(identifier)
        was_root = self.roots.is_root(source)
        target = source.with_name(self._validate_name(name))
        # Capture the registry-resolved spelling before the source disappears.
        old_location, new_location = str(source), str(target)
        if source.name == target.name:
            parent_id = None if was_root else self.roots.remember(source.parent)
            return self.directories.metadata(source, parent_id)
        case_only = (
            source.name.casefold() == target.name.casefold()
            and target.exists()
            and source.samefile(target)
        )
        if case_only:
            temporary = source.with_name(f".{source.name}.{uuid.uuid4().hex}.rename")
            self._ensure_available(temporary)
            source.rename(temporary)
            try:
                temporary.rename(target)
            except OSError:
                temporary.rename(source)
                raise
        else:
            self._ensure_available(target)
            source.rename(target)
        self.roots.replace(source, target)
        try:
            self.on_path_moved(old_location, new_location)
        except OSError:
            # The real rename succeeded; optional Quick Access persistence is
            # best-effort and must not misreport filesystem state.
            pass
        parent_id = None if was_root else self.roots.remember(target.parent)
        item = self.directories.metadata(target, parent_id)
        item["operationToken"] = self._remember_operation(source, target, "rename")
        return item

    def copy(self, identifier: str, destination_id: str) -> dict[str, object]:
        source, destination = self.roots.path_for(identifier), self.roots.get(destination_id)
        target = destination / source.name
        self._reject_recursive(source, destination)
        self._ensure_available(target)
        if source.is_dir():
            self._reject_linked_tree(source)
            self._copy_tree(source, target)
        else:
            shutil.copy2(source, target)
        item = self.directories.metadata(target, destination_id)
        item["operationToken"] = self._remember_creation(
            source, target, "copy", item
        )
        return item

    def create_folder(self, parent_id: str, name: object) -> dict[str, object]:
        parent = self.roots.get(parent_id)
        target = parent / self._validate_name(name)
        self._ensure_available(target)
        target.mkdir()
        item = self.directories.metadata(target, parent_id)
        item["operationToken"] = self._remember_creation(
            None, target, "create_folder", item
        )
        return item

    def move(self, identifier: str, destination_id: str) -> dict[str, object]:
        source, destination = self.roots.path_for(identifier), self.roots.get(destination_id)
        if self.roots.is_root(source):
            raise FileOperationError("A selected root cannot be moved; move its contents instead")
        target = destination / source.name
        # Both values derive from authorized, resolved locations before mutation.
        old_location, new_location = str(source), str(target)
        if source.parent == destination:
            raise FileOperationError("Item is already in that folder")
        self._reject_recursive(source, destination)
        self._ensure_available(target)
        shutil.move(str(source), str(target))
        self.roots.replace(source, target)
        try:
            self.on_path_moved(old_location, new_location)
        except OSError:
            # The real move succeeded; optional Quick Access persistence is
            # best-effort and must not misreport filesystem state.
            pass
        item = self.directories.metadata(target, destination_id)
        item["operationToken"] = self._remember_operation(source, target, "move")
        return item

    def _remember_operation(self, original: Path, changed: Path, kind: str) -> str:
        token = uuid.uuid4().hex
        with self._receipt_lock:
            self._receipts[token] = {
                "original": original, "changed": changed, "kind": kind,
                "identity": self._identity(changed), "applied": True,
            }
        return token

    def _remember_creation(
        self, source: Path | None, target: Path, kind: str, item: dict[str, object]
    ) -> str:
        token = uuid.uuid4().hex
        with self._receipt_lock:
            self._receipts[token] = {
                "source": source,
                "changed": target,
                "kind": kind,
                "identity": self._identity(target),
                "snapshot": self._snapshot(target) if kind == "copy" else None,
                "item": dict(item),
                "applied": True,
            }
        return token

    @staticmethod
    def _identity(path: Path) -> tuple[int, int, int]:
        """Use stable OS object identity; file contents and timestamps are irrelevant."""
        details = path.stat()
        return details.st_dev, details.st_ino, stat.S_IFMT(details.st_mode)

    @classmethod
    def _snapshot(cls, path: Path) -> bytes:
        """Hash tree structure, object identities, and every copied file's bytes."""
        digest = hashlib.sha256()

        def visit(entry: Path, relative: str) -> None:
            if cls._is_filesystem_link(entry):
                raise FileOperationError("Copied result contains a filesystem link")
            identity = cls._identity(entry)
            if entry.is_dir():
                digest.update(
                    b"D\0"
                    + relative.encode("utf-8", "surrogateescape")
                    + repr(identity).encode()
                )
                with os.scandir(entry) as children:
                    names = sorted(child.name for child in children)
                for name in names:
                    visit(entry / name, f"{relative}/{name}")
            elif entry.is_file():
                digest.update(
                    b"F\0"
                    + relative.encode("utf-8", "surrogateescape")
                    + repr(identity).encode()
                )
                with entry.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            else:
                raise FileOperationError("Copied result contains an unsupported object")

        visit(path, "")
        return digest.digest()

    def _authorized_exact(self, path: Path, code: str, message: str) -> None:
        try:
            authorized = self.roots.authorize_existing_descendant(path)
        except (OSError, PermissionError):
            raise FileOperationConflict(code, message) from None
        if authorized != path:
            raise FileOperationConflict(code, "Expected location was redirected")

    def _creation_replay(
        self, receipt: dict[str, object], undo: bool, code: str
    ) -> dict[str, object]:
        target = receipt["changed"]
        assert isinstance(target, Path)
        kind = receipt["kind"]
        if undo:
            self._authorized_exact(target, code, "Created item is no longer authorized")
            try:
                unchanged = self._identity(target) == receipt["identity"]
                if kind == "copy":
                    unchanged = unchanged and self._snapshot(target) == receipt["snapshot"]
                elif kind == "create_folder":
                    unchanged = unchanged and target.is_dir() and not any(target.iterdir())
            except (OSError, FileOperationError):
                unchanged = False
            if not unchanged:
                raise FileOperationConflict(code, "Created item was replaced or modified")
            quarantine = target.with_name(f".{target.name}.{uuid.uuid4().hex}.undo")
            try:
                target.rename(quarantine)
                unchanged = self._identity(quarantine) == receipt["identity"]
                if kind == "copy":
                    unchanged = unchanged and self._snapshot(quarantine) == receipt["snapshot"]
                else:
                    unchanged = unchanged and quarantine.is_dir() and not any(quarantine.iterdir())
                if not unchanged:
                    quarantine.rename(target)
                    raise FileOperationConflict(code, "Created item changed during Undo")
                if quarantine.is_dir():
                    if kind == "copy":
                        shutil.rmtree(quarantine)
                    else:
                        quarantine.rmdir()
                else:
                    quarantine.unlink()
            except FileOperationConflict:
                raise
            except OSError:
                if quarantine.exists() and not target.exists():
                    quarantine.rename(target)
                raise FileOperationConflict(code, "Created item could not be removed safely") from None
            receipt["applied"] = False
            return {"item": receipt["item"], "kind": kind, "applied": False}

        try:
            self._authorized_exact(target.parent, code, "Destination parent is no longer authorized")
        except FileOperationConflict:
            raise
        if target.exists() or target.is_symlink():
            raise FileOperationConflict(code, "Destination is occupied")
        try:
            if kind == "create_folder":
                target.mkdir()
            else:
                source = receipt["source"]
                assert isinstance(source, Path)
                self._authorized_exact(source, code, "Copy source is no longer authorized")
                self._reject_recursive(source, target.parent)
                if source.is_dir():
                    self._reject_linked_tree(source)
                    self._copy_tree(source, target)
                elif source.is_file() and not self._is_filesystem_link(source):
                    shutil.copy2(source, target)
                else:
                    raise FileOperationError("Copy source is unavailable")
            parent_id = self.roots.remember(target.parent)
            item = self.directories.metadata(target, parent_id)
            receipt["identity"] = self._identity(target)
            receipt["snapshot"] = self._snapshot(target) if kind == "copy" else None
            receipt["item"] = dict(item)
            receipt["applied"] = True
            return {"item": item, "kind": kind, "applied": True}
        except (OSError, PermissionError, FileOperationError):
            raise FileOperationConflict(code, "Operation cannot be replayed safely") from None

    def replay(self, token: object, direction: object) -> dict[str, object]:
        """Replay a server-held receipt; paths are never accepted from the client."""
        if not isinstance(token, str) or not isinstance(direction, str):
            raise FileOperationError("A valid operation receipt is required")
        with self._receipt_lock:
            receipt = self._receipts.get(token)
            if receipt is None:
                raise FileOperationError("Unknown or expired operation receipt")
            undo = direction == "undo"
            if not undo and direction != "redo":
                raise FileOperationError("Direction must be undo or redo")
            expected_applied = undo
            code = "undo_conflict" if undo else "redo_conflict"
            if receipt["applied"] is not expected_applied:
                raise FileOperationConflict(code, "Operation is not available in that direction")
            if receipt["kind"] in {"copy", "create_folder"}:
                return self._creation_replay(receipt, undo, code)
            source = receipt["changed"] if undo else receipt["original"]
            target = receipt["original"] if undo else receipt["changed"]
            assert isinstance(source, Path) and isinstance(target, Path)
            try:
                authorized_source = self.roots.authorize_existing_descendant(source)
            except (OSError, PermissionError):
                raise FileOperationConflict(code, "Expected source is no longer authorized") from None
            if authorized_source != source:
                raise FileOperationConflict(code, "Expected source location was redirected")
            if self._identity(source) != receipt["identity"]:
                raise FileOperationConflict(code, "Expected source was replaced")
            if not self.roots.is_root(source):
                try:
                    authorized_parent = self.roots.authorize_existing_descendant(target.parent)
                except (OSError, PermissionError):
                    raise FileOperationConflict(code, "Destination parent is no longer authorized") from None
                if authorized_parent != target.parent:
                    raise FileOperationConflict(code, "Destination location was redirected")
            case_only = source.name.casefold() == target.name.casefold() and target.exists() and source.samefile(target)
            if not case_only and (target.exists() or target.is_symlink()):
                raise FileOperationConflict(code, "Destination is occupied")
            kind = receipt["kind"]
            if kind == "move":
                shutil.move(str(source), str(target))
            elif case_only:
                temporary = source.with_name(f".{source.name}.{uuid.uuid4().hex}.rename")
                self._ensure_available(temporary); source.rename(temporary)
                try: temporary.rename(target)
                except OSError:
                    temporary.rename(source); raise
            else:
                source.rename(target)
            # shutil.move may copy across volumes, producing a new inode. Track
            # the object created by that successful move for the next replay.
            receipt["identity"] = self._identity(target)
            self.roots.replace(source, target)
            try: self.on_path_moved(str(source), str(target))
            except OSError: pass
            receipt["applied"] = not undo
            parent_id = None if self.roots.is_root(target) else self.roots.remember(target.parent)
            item = self.directories.metadata(target, parent_id)
            return {"item": item, "kind": receipt["kind"]}
