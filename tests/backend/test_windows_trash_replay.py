import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from backend.filesystem.trash import (
    RecycleReplay,
    RecycleState,
    TrashConflict,
    TrashError,
    TrashNotRecoverable,
)


class FakeAdapter:
    def __init__(self) -> None:
        self.next_identity = b"pidl-1"
        self.recycled: dict[bytes, Path] = {}
        self.fail_recycle = False
        self.fail_restore = False

    def recycle(self, path: Path) -> bytes:
        if self.fail_recycle:
            raise TrashError("injected recycle failure")
        identity = self.next_identity
        if path.is_dir():
            raise AssertionError("unit fake supports files only")
        holding = path.with_name(f".{identity.hex()}.fake-recycle")
        path.rename(holding)
        self.recycled[identity] = holding
        return identity

    def restore(self, identity: bytes, parent: Path, name: str) -> None:
        if self.fail_restore:
            raise TrashError("injected restore failure")
        holding = self.recycled.pop(identity, None)
        if holding is None or not holding.exists():
            raise TrashError("opaque identity is missing or replaced")
        target = parent / name
        holding.rename(target)


class WindowsTrashReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "sentinel.txt"
        self.path.write_bytes(b"unique sentinel")
        self.adapter = FakeAdapter()
        self.replay = RecycleReplay(self.adapter)

    def test_recycle_restore_and_redo_replaces_identity(self) -> None:
        receipt = self.replay.recycle(self.path)
        self.assertEqual(receipt.state, RecycleState.RECYCLED)
        self.assertFalse(self.path.exists())

        restored = self.replay.restore(receipt)
        self.assertEqual(restored.state, RecycleState.RESTORED)
        self.assertEqual(self.path.read_bytes(), b"unique sentinel")
        self.adapter.next_identity = b"pidl-2"

        redone = self.replay.redo(restored)
        self.assertEqual(redone.state, RecycleState.RECYCLED)
        self.assertEqual(redone.recycled_identity, b"pidl-2")
        self.assertNotEqual(redone.recycled_identity, receipt.recycled_identity)

    def test_occupied_restore_destination_changes_nothing(self) -> None:
        receipt = self.replay.recycle(self.path)
        self.path.write_bytes(b"occupant")

        with self.assertRaisesRegex(TrashConflict, "occupied"):
            self.replay.restore(receipt)
        self.assertEqual(receipt.state, RecycleState.RECYCLED)
        self.assertEqual(self.path.read_bytes(), b"occupant")

    def test_missing_opaque_identity_leaves_direction_recycled(self) -> None:
        receipt = self.replay.recycle(self.path)
        self.adapter.recycled.clear()

        with self.assertRaisesRegex(TrashError, "identity"):
            self.replay.restore(receipt)
        self.assertEqual(receipt.state, RecycleState.RECYCLED)
        self.assertFalse(self.path.exists())

    def test_replaced_opaque_identity_is_not_used_as_a_name_search(self) -> None:
        receipt = self.replay.recycle(self.path)
        replaced = replace(receipt, recycled_identity=b"some-other-pidl")

        with self.assertRaisesRegex(TrashError, "identity"):
            self.replay.restore(replaced)
        self.assertEqual(replaced.state, RecycleState.RECYCLED)
        self.assertFalse(self.path.exists())

    def test_failed_redo_leaves_direction_restored(self) -> None:
        restored = self.replay.restore(self.replay.recycle(self.path))
        self.adapter.fail_recycle = True

        with self.assertRaisesRegex(TrashError, "injected"):
            self.replay.redo(restored)
        self.assertEqual(restored.state, RecycleState.RESTORED)
        self.assertTrue(self.path.exists())

    def test_empty_post_delete_identity_is_not_recoverable(self) -> None:
        self.adapter.next_identity = b""
        with self.assertRaises(TrashNotRecoverable):
            self.replay.recycle(self.path)

    def test_replaced_restored_object_is_rejected_before_redo(self) -> None:
        restored = self.replay.restore(self.replay.recycle(self.path))
        self.path.write_bytes(b"different size")

        with self.assertRaisesRegex(TrashConflict, "replaced"):
            self.replay.redo(restored)
        self.assertEqual(restored.state, RecycleState.RESTORED)


if __name__ == "__main__":
    unittest.main()
