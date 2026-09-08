"""State and orchestration for the Windows Recycle Bin experiment.

Nothing here is connected to the HTTP server or normal filesystem operations.
The adapter seam keeps state-transition tests safe and platform independent.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Protocol


class TrashError(RuntimeError):
    """A native recycle or replay operation could not be proved successful."""


class TrashNotRecoverable(TrashError):
    """The Shell did not return an object which can be replayed exactly."""


class TrashConflict(TrashError):
    """Replay would overwrite, merge, or act on an unexpected object."""


class RecycleState(Enum):
    RECYCLED = "recycled"
    RESTORED = "restored"


@dataclass(frozen=True)
class ObjectVerification:
    device: int
    inode: int
    kind: int
    size: int

    @classmethod
    def capture(cls, path: Path) -> "ObjectVerification":
        details = path.stat(follow_symlinks=False)
        # Windows maps these fields to the volume serial number and file index.
        # They survive an in-volume Shell move and reject a same-sized replacement.
        return cls(details.st_dev, details.st_ino, stat.S_IFMT(details.st_mode), details.st_size)

    def matches(self, path: Path) -> bool:
        try:
            current = self.capture(path)
        except (FileNotFoundError, OSError):
            return False
        return current == self


@dataclass(frozen=True)
class RecycleReceipt:
    """Server-only replay data; ``recycled_identity`` must never enter an API."""

    original_path: Path
    original_parent: Path
    original_name: str
    verification: ObjectVerification
    recycled_identity: bytes | None
    state: RecycleState


class RecycleAdapter(Protocol):
    def recycle(self, path: Path) -> bytes: ...

    def restore(self, recycled_identity: bytes, parent: Path, name: str) -> None: ...


class RecycleReplay:
    """Pure state machine around a platform adapter.

    Receipts are immutable. Consequently a native exception cannot accidentally
    flip Undo/Redo direction or discard the last known opaque identity.
    """

    def __init__(self, adapter: RecycleAdapter) -> None:
        self._adapter = adapter

    def recycle(self, path: os.PathLike[str] | str) -> RecycleReceipt:
        original = Path(path).absolute()
        verification = ObjectVerification.capture(original)
        identity = self._adapter.recycle(original)
        if not identity:
            raise TrashNotRecoverable(
                "The Shell did not return a recoverable Recycle Bin object"
            )
        return RecycleReceipt(
            original_path=original,
            original_parent=original.parent,
            original_name=original.name,
            verification=verification,
            recycled_identity=bytes(identity),
            state=RecycleState.RECYCLED,
        )

    def restore(self, receipt: RecycleReceipt) -> RecycleReceipt:
        if receipt.state is not RecycleState.RECYCLED or not receipt.recycled_identity:
            raise TrashConflict("Receipt is not in the recycled state")
        target = receipt.original_path
        if target.exists() or target.is_symlink():
            raise TrashConflict(f"Restore destination is occupied: {target}")
        self._adapter.restore(
            receipt.recycled_identity, receipt.original_parent, receipt.original_name
        )
        if not receipt.verification.matches(target):
            raise TrashConflict("Restored object failed verification")
        return replace(receipt, recycled_identity=None, state=RecycleState.RESTORED)

    def redo(self, receipt: RecycleReceipt) -> RecycleReceipt:
        if receipt.state is not RecycleState.RESTORED:
            raise TrashConflict("Receipt is not in the restored state")
        if not receipt.verification.matches(receipt.original_path):
            raise TrashConflict("Restored object is missing or was replaced")
        new_identity = self._adapter.recycle(receipt.original_path)
        if not new_identity:
            raise TrashNotRecoverable(
                "The Shell did not return a recoverable Recycle Bin object"
            )
        return replace(
            receipt,
            recycled_identity=bytes(new_identity),
            state=RecycleState.RECYCLED,
        )
