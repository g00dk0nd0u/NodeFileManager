"""Focused tests for authorized file-management services."""
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.opener import FileOpener
from backend.filesystem.operations import FileOperationConflict, FileOperationError, FileOperations
from backend.filesystem.roots import RootRegistry
from backend.navigation.locations import canonical_location


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
        self.assertIsInstance(self.file_item["modifiedTime"], float)
        self.file.unlink()
        self.assertEqual(self.directories.contents(str(self.source_item["id"]))["files"], [])

    def test_rename_file_and_folder_and_reject_invalid_names(self):
        renamed = self.operations.rename(str(self.file_item["id"]), "renamed.txt"); self.assertTrue(Path(str(renamed["path"])).is_file())
        folder = self.operations.rename(str(self.destination_item["id"]), "archive"); self.assertTrue(Path(str(folder["path"])).is_dir())
        for name in ("", "../escape", "bad/name", "bad\\name"):
            with self.subTest(name=name), self.assertRaises(FileOperationError): self.operations.rename(str(renamed["id"]), name)

    def test_case_only_rename_succeeds_and_real_collision_is_rejected(self):
        case_item = self.operations.rename(str(self.file_item["id"]), "Report.txt")
        renamed = self.operations.rename(str(case_item["id"]), "report.txt")
        self.assertEqual(Path(str(renamed["path"])).name, "report.txt")
        (self.source / "occupied.txt").write_text("collision")
        with self.assertRaises(FileExistsError):
            self.operations.rename(str(renamed["id"]), "occupied.txt")

    def test_create_folder_validates_name_and_collision(self):
        created = self.operations.create_folder(str(self.source_item["id"]), "Test_New")
        self.assertTrue(Path(str(created["path"])).is_dir())
        with self.assertRaises(FileExistsError):
            self.operations.create_folder(str(self.source_item["id"]), "Test_New")
        for name in ("", ".", "..", "bad/name", "bad\\name"):
            with self.subTest(name=name), self.assertRaises(FileOperationError):
                self.operations.create_folder(str(self.source_item["id"]), name)

    def test_create_folder_undo_redo_and_conflicts(self):
        created = self.operations.create_folder(str(self.destination_item["id"]), "NewFolder")
        target = self.destination / "NewFolder"; token = created["operationToken"]
        self.assertFalse(self.operations.replay(token, "undo")["applied"]); self.assertFalse(target.exists())
        self.assertTrue(self.operations.replay(token, "redo")["applied"]); self.assertTrue(target.is_dir())
        (target / "unknown.txt").write_text("keep")
        with self.assertRaises(FileOperationConflict) as conflict: self.operations.replay(token, "undo")
        self.assertEqual("undo_conflict", conflict.exception.code); self.assertEqual("keep", (target / "unknown.txt").read_text())
        (target / "unknown.txt").unlink(); self.operations.replay(token, "undo"); target.mkdir()
        with self.assertRaises(FileOperationConflict) as conflict: self.operations.replay(token, "redo")
        self.assertEqual("redo_conflict", conflict.exception.code); self.assertTrue(target.is_dir())

    def test_create_folder_replacement_and_redirect_block_undo(self):
        created = self.operations.create_folder(str(self.destination_item["id"]), "NewFolder")
        target = self.destination / "NewFolder"; replacement = self.destination / "replacement"
        replacement.mkdir(); target.rmdir(); replacement.rename(target)
        with self.assertRaises(FileOperationConflict) as conflict: self.operations.replay(created["operationToken"], "undo")
        self.assertEqual("undo_conflict", conflict.exception.code); self.assertTrue(target.is_dir())
        target.rmdir()
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "NewFolder"; external.mkdir()
            try: target.symlink_to(external, target_is_directory=True)
            except (NotImplementedError, OSError) as error: self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(FileOperationConflict): self.operations.replay(created["operationToken"], "undo")
            self.assertTrue(external.is_dir())

    def test_copy_move_collisions_and_recursive_copy(self):
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"])); self.assertEqual(Path(str(copied["path"])).read_text(), "content")
        with self.assertRaises(FileExistsError): self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))
        Path(str(copied["path"])).rename(self.destination / "copied.txt")
        moved = self.operations.move(str(self.file_item["id"]), str(self.destination_item["id"])); self.assertFalse(self.file.exists()); self.assertTrue(Path(str(moved["path"])).exists())
        nested = self.source / "nested"; nested.mkdir(); nested_item = self.directories.metadata(nested, str(self.source_item["id"]))
        with self.assertRaises(FileOperationError): self.operations.copy(str(self.source_item["id"]), str(nested_item["id"]))
        with self.assertRaises(PermissionError): self.operations.move("../../outside", str(self.destination_item["id"]))

    def test_copy_file_undo_redo_and_content_conflicts(self):
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))
        target = self.destination / "report.txt"; token = copied["operationToken"]
        self.operations.replay(token, "undo"); self.assertFalse(target.exists())
        self.operations.replay(token, "redo"); self.assertEqual("content", target.read_text())
        target.write_text("modified")
        with self.assertRaises(FileOperationConflict) as conflict: self.operations.replay(token, "undo")
        self.assertEqual("undo_conflict", conflict.exception.code); self.assertEqual("modified", target.read_text())
        target.unlink(); self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))

    def test_copy_file_replacement_and_occupied_redo_are_preserved(self):
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"]))
        target = self.destination / "report.txt"; token = copied["operationToken"]
        replacement = self.destination / "replacement"; replacement.write_text("external"); replacement.replace(target)
        with self.assertRaises(FileOperationConflict): self.operations.replay(token, "undo")
        self.assertEqual("external", target.read_text()); target.unlink()
        copied = self.operations.copy(str(self.file_item["id"]), str(self.destination_item["id"])); token = copied["operationToken"]
        self.operations.replay(token, "undo"); target.write_text("occupied")
        with self.assertRaises(FileOperationConflict) as conflict: self.operations.replay(token, "redo")
        self.assertEqual("redo_conflict", conflict.exception.code); self.assertEqual("occupied", target.read_text())

    def test_copy_directory_manifest_blocks_tree_changes_without_deleting_unknown_content(self):
        nested = self.source / "nested"; nested.mkdir(); child = nested / "child.txt"; child.write_text("child")
        source_item = self.directories.metadata(nested, str(self.source_item["id"])); target = self.destination / "nested"
        for mutation in ("add", "modify", "remove"):
            with self.subTest(mutation=mutation):
                copied = self.operations.copy(str(source_item["id"]), str(self.destination_item["id"])); token = copied["operationToken"]
                if mutation == "add": (target / "unknown.txt").write_text("keep")
                elif mutation == "modify": (target / "child.txt").write_text("changed")
                else: (target / "child.txt").unlink()
                with self.assertRaises(FileOperationConflict) as conflict: self.operations.replay(token, "undo")
                self.assertEqual("undo_conflict", conflict.exception.code); self.assertTrue(target.exists())
                if mutation == "add": self.assertEqual("keep", (target / "unknown.txt").read_text())
                shutil.rmtree(target)

    def test_copy_directory_undo_redo_and_redirect_conflict(self):
        nested = self.source / "nested"; nested.mkdir(); (nested / "child.txt").write_text("child")
        source_item = self.directories.metadata(nested, str(self.source_item["id"])); target = self.destination / "nested"
        copied = self.operations.copy(str(source_item["id"]), str(self.destination_item["id"])); token = copied["operationToken"]
        self.operations.replay(token, "undo"); self.assertFalse(target.exists())
        self.operations.replay(token, "redo"); self.assertEqual("child", (target / "child.txt").read_text())
        shutil.rmtree(target)
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "nested"; external.mkdir(); (external / "unknown.txt").write_text("keep")
            try: target.symlink_to(external, target_is_directory=True)
            except (NotImplementedError, OSError) as error: self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(FileOperationConflict): self.operations.replay(token, "undo")
            self.assertEqual("keep", (external / "unknown.txt").read_text())

    def test_folder_copy_rejects_symlink_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside, "external"); external.mkdir(); Path(external, "secret.txt").write_text("secret")
            link = self.source / "external-link"
            try:
                link.symlink_to(external, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaisesRegex(FileOperationError, "filesystem links"):
                self.operations.copy(str(self.source_item["id"]), str(self.destination_item["id"]))
            self.assertFalse((self.destination / self.source.name).exists())

    def test_folder_copy_rejects_junction_check(self):
        with patch.object(Path, "is_junction", return_value=True):
            with self.assertRaisesRegex(FileOperationError, "filesystem links"):
                self.operations.copy(str(self.source_item["id"]), str(self.destination_item["id"]))
        self.assertFalse((self.destination / self.source.name).exists())

    def test_opener_accepts_only_authorized_existing_files(self):
        opener = FileOpener(self.roots)
        with patch("backend.filesystem.opener.sys.platform", "darwin"), patch("backend.filesystem.opener.subprocess.Popen") as popen: opener.open(str(self.file_item["id"]))
        popen.assert_called_once_with(["/usr/bin/open", str(self.file.resolve())], close_fds=True)
        with self.assertRaises(IsADirectoryError): opener.open(str(self.source_item["id"]))
        self.file.unlink()
        with self.assertRaises(FileNotFoundError): opener.open(str(self.file_item["id"]))

    def test_rename_succeeds_when_navigation_persistence_fails(self):
        operations = FileOperations(self.roots, self.directories, lambda old, new: (_ for _ in ()).throw(OSError("store failed")))
        renamed = operations.rename(str(self.file_item["id"]), "renamed.txt")
        self.assertEqual(canonical_location(str(renamed["path"])), canonical_location(self.source / "renamed.txt"))
        self.assertTrue((self.source / "renamed.txt").is_file())
        self.assertFalse(self.file.exists())

    def test_move_succeeds_when_navigation_persistence_fails(self):
        operations = FileOperations(self.roots, self.directories, lambda old, new: (_ for _ in ()).throw(OSError("store failed")))
        moved = operations.move(str(self.file_item["id"]), str(self.destination_item["id"]))
        self.assertEqual(canonical_location(str(moved["path"])), canonical_location(self.destination / "report.txt"))
        self.assertTrue((self.destination / "report.txt").is_file())
        self.assertFalse(self.file.exists())

    def test_rename_undo_redo_and_conflict(self):
        renamed = self.operations.rename(str(self.file_item["id"]), "renamed.txt")
        token = renamed["operationToken"]
        undone = self.operations.replay(token, "undo")["item"]
        self.assertEqual(Path(str(undone["path"])), self.file.resolve())
        redone = self.operations.replay(token, "redo")["item"]
        self.assertEqual(Path(str(redone["path"])), (self.source / "renamed.txt").resolve())
        (self.source / "report.txt").write_text("occupied")
        with self.assertRaises(FileOperationConflict) as conflict:
            self.operations.replay(token, "undo")
        self.assertEqual(conflict.exception.code, "undo_conflict")
        self.assertTrue((self.source / "renamed.txt").exists())

    def test_move_file_and_folder_undo_redo_preserve_registry(self):
        for identifier, original in ((str(self.file_item["id"]), self.file), (str(self.source_item["id"]), self.source)):
            with self.subTest(original=original):
                moved = self.operations.move(identifier, str(self.destination_item["id"]))
                token = moved["operationToken"]
                undone = self.operations.replay(token, "undo")["item"]
                self.assertEqual(Path(str(undone["path"])), original.resolve())
                self.assertEqual(self.roots.path_for(str(undone["id"])), original.resolve())
                redone = self.operations.replay(token, "redo")["item"]
                self.assertEqual(Path(str(redone["path"])), (self.destination / original.name).resolve())
                self.operations.replay(token, "undo")

    def test_move_occupied_original_blocks_undo_but_receipt_remains_available(self):
        moved = self.operations.move(str(self.file_item["id"]), str(self.destination_item["id"]))
        self.file.write_text("replacement")
        with self.assertRaises(FileOperationConflict) as conflict:
            self.operations.replay(moved["operationToken"], "undo")
        self.assertEqual(conflict.exception.code, "undo_conflict")
        self.file.unlink()
        undone = self.operations.replay(moved["operationToken"], "undo")["item"]
        self.assertEqual(Path(str(undone["path"])), self.file.resolve())

    def test_replay_rejects_replacement_objects_without_flipping_direction(self):
        for operation in ("rename", "move"):
            with self.subTest(operation=operation):
                if operation == "rename":
                    changed = self.operations.rename(str(self.file_item["id"]), "renamed.txt")
                else:
                    changed = self.operations.move(str(self.file_item["id"]), str(self.destination_item["id"]))
                changed_path = Path(str(changed["path"]))
                replacement = changed_path.with_name("replacement.tmp")
                replacement.write_text("replacement"); replacement.replace(changed_path)
                with self.assertRaises(FileOperationConflict) as conflict:
                    self.operations.replay(changed["operationToken"], "undo")
                self.assertEqual(conflict.exception.code, "undo_conflict")
                self.assertEqual(changed_path.read_text(), "replacement")
                changed_path.unlink(); self.file.write_text("reset")
                self.file_item = self.directories.metadata(self.file, str(self.source_item["id"]))

    def test_in_place_file_edit_does_not_block_undo(self):
        renamed = self.operations.rename(str(self.file_item["id"]), "renamed.txt")
        Path(str(renamed["path"])).write_text("edited in place")
        undone = self.operations.replay(renamed["operationToken"], "undo")["item"]
        self.assertEqual(Path(str(undone["path"])).read_text(), "edited in place")

    def test_redo_rejects_replacement_at_expected_source(self):
        renamed = self.operations.rename(str(self.file_item["id"]), "renamed.txt")
        self.operations.replay(renamed["operationToken"], "undo")
        replacement = self.source / "replacement.tmp"
        replacement.write_text("replacement"); replacement.replace(self.file)
        with self.assertRaises(FileOperationConflict) as conflict:
            self.operations.replay(renamed["operationToken"], "redo")
        self.assertEqual(conflict.exception.code, "redo_conflict")
        self.assertFalse((self.source / "renamed.txt").exists())

    def test_move_replay_uses_shutil_move_and_migrates_navigation(self):
        migrated = []
        operations = FileOperations(self.roots, self.directories, lambda old, new: migrated.append((old, new)))
        moved = operations.move(str(self.file_item["id"]), str(self.destination_item["id"]))
        expected_source = (self.destination / "report.txt").resolve()
        expected_target = self.file.parent.resolve() / self.file.name
        normalized_calls = []
        real_move = shutil.move
        def normalized_move(source, target):
            normalized_calls.append((Path(source).resolve(strict=True), Path(target).parent.resolve() / Path(target).name))
            return real_move(source, target)
        with patch("backend.filesystem.operations.shutil.move", side_effect=normalized_move) as replay_move:
            undone = operations.replay(moved["operationToken"], "undo")["item"]
        self.assertEqual(replay_move.call_count, 1)
        self.assertEqual(normalized_calls, [(expected_source, expected_target)])
        self.assertEqual(self.roots.path_for(str(undone["id"])), self.file.resolve())
        migrated_old, migrated_new = (Path(location).resolve() for location in migrated[-1])
        self.assertEqual(migrated_old, (self.destination / "report.txt").resolve())
        self.assertEqual(migrated_new, self.file.resolve())

    def test_replay_rejects_source_redirected_outside_root_by_ancestor_symlink(self):
        nested = self.source / "nested"; nested.mkdir()
        item = self.directories.metadata(nested, str(self.source_item["id"]))
        file_path = nested / "inside.txt"; file_path.write_text("content")
        file_item = self.directories.metadata(file_path, str(item["id"]))
        renamed = self.operations.rename(str(file_item["id"]), "renamed.txt")
        with tempfile.TemporaryDirectory() as outside_directory:
            outside = Path(outside_directory) / "nested"
            nested.rename(outside)
            try:
                nested.symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                outside.rename(nested)
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(FileOperationConflict) as conflict:
                self.operations.replay(renamed["operationToken"], "undo")
            self.assertEqual(conflict.exception.code, "undo_conflict")
            self.assertTrue((outside / "renamed.txt").exists())
            self.assertFalse((outside / "inside.txt").exists())
            nested.unlink(); outside.rename(nested)

    def test_move_replay_rejects_destination_redirected_outside_root(self):
        moved = self.operations.move(str(self.file_item["id"]), str(self.destination_item["id"]))
        with tempfile.TemporaryDirectory() as outside_directory:
            outside = Path(outside_directory) / "source"
            self.source.rename(outside)
            try:
                self.source.symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                outside.rename(self.source)
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaises(FileOperationConflict) as conflict:
                self.operations.replay(moved["operationToken"], "undo")
            self.assertEqual(conflict.exception.code, "undo_conflict")
            self.assertTrue((self.destination / "report.txt").exists())
            self.assertFalse((outside / "report.txt").exists())
            self.source.unlink(); outside.rename(self.source)


if __name__ == "__main__": unittest.main()
