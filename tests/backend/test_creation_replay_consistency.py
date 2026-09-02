"""Regression tests for creation replay state after physical filesystem transitions."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.operations import FileOperationConflict, FileOperationError, FileOperations
from backend.filesystem.roots import RootRegistry


class CreationReplayConsistencyTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        self.file = self.source / "report.txt"
        self.file.write_text("content")

        self.roots = RootRegistry()
        self.directories = DirectoryService(self.roots)
        root_item = self.directories.select(str(self.root))
        folders = self.directories.contents(str(root_item["id"]))["folders"]
        self.source_item = next(item for item in folders if item["name"] == "source")
        self.destination_item = next(item for item in folders if item["name"] == "destination")
        self.file_item = self.directories.contents(str(self.source_item["id"]))["files"][0]
        self.operations = FileOperations(self.roots, self.directories)

    def tearDown(self):
        self.temporary.cleanup()

    def test_copy_undo_post_rename_snapshot_failure_rolls_back(self):
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))
        token = copied["operationToken"]
        target = self.destination / "report.txt"
        receipt = self.operations._receipts[token]
        snapshot = receipt["snapshot"]

        with patch.object(
            self.operations,
            "_snapshot",
            side_effect=[snapshot, FileOperationError("late verification failure")],
        ):
            with self.assertRaises(FileOperationConflict) as conflict:
                self.operations.replay(token, "undo")

        self.assertEqual("undo_conflict", conflict.exception.code)
        self.assertTrue(target.is_file())
        self.assertEqual("content", target.read_text())
        self.assertTrue(receipt["applied"])
        self.assertIsNone(receipt["quarantine"])
        self.assertEqual(set(), self.directories._hidden_paths)
        self.assertFalse(any(path.name.startswith(".nfm-undo-") for path in self.destination.iterdir()))

    def test_copy_redo_post_rename_snapshot_failure_restores_quarantine(self):
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))
        token = copied["operationToken"]
        target = self.destination / "report.txt"
        self.operations.replay(token, "undo")
        receipt = self.operations._receipts[token]
        quarantine = receipt["quarantine"]
        snapshot = receipt["snapshot"]
        self.assertIsInstance(quarantine, Path)

        with patch.object(
            self.operations,
            "_snapshot",
            side_effect=[snapshot, FileOperationError("late verification failure")],
        ):
            with self.assertRaises(FileOperationConflict) as conflict:
                self.operations.replay(token, "redo")

        self.assertEqual("redo_conflict", conflict.exception.code)
        self.assertFalse(target.exists())
        self.assertTrue(quarantine.exists())
        self.assertFalse(receipt["applied"])
        self.assertEqual(quarantine, receipt["quarantine"])
        self.assertTrue(self.directories._is_hidden(quarantine))

    def test_copy_redo_metadata_failure_does_not_reverse_success(self):
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))
        token = copied["operationToken"]
        target = self.destination / "report.txt"
        self.operations.replay(token, "undo")
        receipt = self.operations._receipts[token]
        quarantine = receipt["quarantine"]

        with patch.object(self.directories, "metadata", side_effect=RuntimeError("metadata failed")):
            result = self.operations.replay(token, "redo")

        self.assertTrue(result["applied"])
        self.assertTrue(target.is_file())
        self.assertEqual("content", target.read_text())
        self.assertTrue(receipt["applied"])
        self.assertIsNone(receipt["quarantine"])
        self.assertFalse(quarantine.exists())
        self.assertFalse(self.directories._is_hidden(quarantine))

    def test_create_folder_redo_metadata_failure_keeps_created_state(self):
        created = self.operations.create_folder(str(self.destination_item["id"]), "NewFolder")
        token = created["operationToken"]
        target = self.destination / "NewFolder"
        self.operations.replay(token, "undo")
        receipt = self.operations._receipts[token]

        with patch.object(self.directories, "metadata", side_effect=RuntimeError("metadata failed")):
            result = self.operations.replay(token, "redo")

        self.assertTrue(result["applied"])
        self.assertTrue(target.is_dir())
        self.assertTrue(receipt["applied"])
        self.assertEqual(self.operations._identity(target), receipt["identity"])


if __name__ == "__main__":
    unittest.main()
