import tempfile
import unittest
from pathlib import Path

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.roots import RootRegistry


class WorkingSetDirectoryApiTest(unittest.TestCase):
    def test_parent_is_derived_from_authorized_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); child = root / "child"; child.mkdir()
            service = DirectoryService(RootRegistry()); selected = service.select(str(child))
            parent = service.parent(str(selected["id"]))
            self.assertEqual(root.resolve(), Path(str(parent["path"])))

    def test_scoped_search_is_bounded_and_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "root"); root.mkdir(); (root / "needle.txt").write_text("x")
            outside = Path(directory, "outside"); outside.mkdir(); (outside / "needle-secret.txt").write_text("x")
            try: (root / "link").symlink_to(outside, target_is_directory=True)
            except OSError: pass
            service = DirectoryService(RootRegistry()); selected = service.select(str(root))
            result = service.search(str(selected["id"]), "needle")
            self.assertEqual(["needle.txt"], [item["name"] for item in result["results"]])

    def test_short_scoped_search_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            service = DirectoryService(RootRegistry()); selected = service.select(directory)
            with self.assertRaises(ValueError): service.search(str(selected["id"]), "x")

    def test_scoped_search_stops_at_traversal_budget_without_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5): (root / f"unrelated-{index}.txt").write_text("x")
            service = DirectoryService(RootRegistry()); selected = service.select(directory)
            result = service.search(str(selected["id"]), "needle", max_entries=2)
            self.assertTrue(result["truncated"])
            self.assertEqual([], result["results"])
