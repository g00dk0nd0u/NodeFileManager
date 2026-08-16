"""Focused tests for authorized file-management services."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.opener import FileOpener
from backend.filesystem.operations import FileOperationError, FileOperations
from backend.filesystem.roots import RootRegistry


class FileOperationsTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        self.source = self.root / "source"; self.destination = self.root / "destination"
        self.source.mkdir(); self.destination.mkdir(); self.file = self.source / "report.txt"; self.file.write_text("content")
        self.roots = RootRegistry(); self.directories = DirectoryService(self.roots); root = self.directories.select(str(self.root))
        folders = self.directories.contents(str(root["id"]))["folders"]
        self.source_item = next(item for item in folders if item["name"] == "source")
        self.destination_item = next(item for item in folders if item["name"] == "destination")
        self.file_item = self.directories.contents(str(self.source_item["id"]))["files"][0]
        self.operations = FileOperations(self.roots, self.directories)

    def tearDown(self): self.temporary.cleanup()

    def test_listing_returns_explicit_file_metadata(self):
        self.assertEqual((self.file_item["kind"], self.file_item["extension"], self.file_item["parentId"]), ("file", ".txt", self.source_item["id"]))
        self.file.unlink()
        self.assertEqual(self.directories.contents(str(self.source_item["id"]))["files"], [])

    def test_rename_file_and_folder_and_reject_invalid_names(self):
        renamed = self.operations.rename(str(self.file_item["id"]), "renamed.txt"); self.assertTrue(Path(str(renamed["path"])).is_file())
        folder = self.operations.rename(str(self.destination_item["id"]), "archive"); self.assertTrue(Path(str(folder["path"])).is_dir())
        for name in ("", "../escape", "bad/name", "bad\\name"):
            with self.subTest(name=name), self.assertRaises(FileOperationError): self.operations.rename(str(renamed["id"]), name)

    def test_copy_move_collisions_and_recursive_copy(self):
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"])); self.assertEqual(Path(str(copied["path"])).read_text(), "content")
        with self.assertRaises(FileExistsError): self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))
        Path(str(copied["path"])).rename(self.destination / "copied.txt")
        moved = self.operations.move(str(self.file_item["id"]), str(self.destination_item["id"])); self.assertFalse(self.file.exists()); self.assertTrue(Path(str(moved["path"])).exists())
        nested = self.source / "nested"; nested.mkdir(); nested_item = self.directories.metadata(nested, str(self.source_item["id"]))
        with self.assertRaises(FileOperationError): self.operations.copy(str(self.source_item["id"]), str(nested_item["id"]))
        with self.assertRaises(PermissionError): self.operations.move("../../outside", str(self.destination_item["id"]))

    def test_opener_accepts_only_authorized_existing_files(self):
        opener = FileOpener(self.roots)
        with patch("backend.filesystem.opener.sys.platform", "darwin"), patch("backend.filesystem.opener.subprocess.Popen") as popen: opener.open(str(self.file_item["id"]))
        popen.assert_called_once_with(["/usr/bin/open", str(self.file.resolve())], close_fds=True)
        with self.assertRaises(IsADirectoryError): opener.open(str(self.source_item["id"]))
        self.file.unlink()
        with self.assertRaises(FileNotFoundError): opener.open(str(self.file_item["id"]))


if __name__ == "__main__": unittest.main()
