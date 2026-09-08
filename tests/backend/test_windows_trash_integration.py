"""Destructive Windows proof, gated to disposable data and explicit opt-in."""

import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from backend.filesystem.trash import RecycleReplay, RecycleState


@unittest.skipUnless(sys.platform == "win32", "requires Windows Shell")
@unittest.skipUnless(
    os.environ.get("NODEFILEMANAGER_RUN_RECYCLE_PROTOTYPE") == "1",
    "set NODEFILEMANAGER_RUN_RECYCLE_PROTOTYPE=1 for the disposable proof",
)
class WindowsRecycleIntegrationTest(unittest.TestCase):
    def test_disposable_recycle_restore_recycle(self) -> None:
        # There is intentionally no path argument: the test can only mutate the
        # uniquely named object it creates under its own TemporaryDirectory.
        from backend.filesystem.trash.windows import WindowsRecycleBinAdapter

        sentinel = f"NodeFileManager recycle proof {uuid.uuid4()}".encode()
        with tempfile.TemporaryDirectory() as temporary:
            disposable = Path(temporary) / f"disposable-{uuid.uuid4()}.txt"
            disposable.write_bytes(sentinel)
            replay = RecycleReplay(WindowsRecycleBinAdapter())

            first = replay.recycle(disposable)
            restored = replay.restore(first)
            self.assertEqual(disposable.read_bytes(), sentinel)
            second = replay.redo(restored)
            self.assertEqual(second.state, RecycleState.RECYCLED)
            self.assertNotEqual(second.recycled_identity, first.recycled_identity)


if __name__ == "__main__":
    unittest.main()
