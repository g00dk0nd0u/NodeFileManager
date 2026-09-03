"""Focused quick-access persistence, ranking, authorization, and search tests."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.operations import FileOperations
from backend.filesystem.roots import RootRegistry
from backend.navigation.locations import canonical_location
from backend.navigation.search import NavigationSearch
from backend.navigation.service import NavigationService
from backend.navigation.store import MAX_USAGE, QuickAccessStore


class NavigationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.base = Path(self.temp.name)
        self.roots = RootRegistry(); self.directories = DirectoryService(self.roots)
        self.store = QuickAccessStore(self.base / "quick_access.json")
        self.now = 2_000_000_000
        self.service = NavigationService(self.roots, self.directories, self.store, lambda: self.now)

    def tearDown(self): self.temp.cleanup()

    def folder(self, name="root"):
        path = self.base / name; path.mkdir(exist_ok=True)
        return path, self.directories.select(str(path))

    def test_favorite_add_remove_and_authorization(self):
        path, folder = self.folder(); result = self.service.toggle(folder["id"])
        self.assertTrue(result["favorite"]); self.assertEqual(result["favorites"][0]["path"], canonical_location(path))
        self.assertFalse(self.service.toggle(folder["id"])["favorite"])
        with self.assertRaises(PermissionError): self.service.toggle("arbitrary")

    def test_explicit_favorite_replay_is_idempotent(self):
        path, folder = self.folder(); added = self.service.toggle(folder["id"]); favorite_id = added["favoriteId"]
        self.assertFalse(self.service.set_favorite(favorite_id, False)["favorite"])
        self.assertEqual(self.service.set_favorite(favorite_id, False)["favorites"], [])
        self.assertTrue(self.service.set_favorite(favorite_id, True)["favorite"])
        replayed = self.service.set_favorite(favorite_id, True)
        self.assertEqual([canonical_location(path)], [item["path"] for item in replayed["favorites"]])

    def test_explicit_favorite_replay_rejects_unknown_identifier(self):
        with self.assertRaises(PermissionError): self.service.set_favorite("arbitrary", True)

    def test_favorite_persists_and_reopens_server_owned_path(self):
        path, folder = self.folder(); self.service.toggle(folder["id"])
        fresh_roots = RootRegistry(); fresh = NavigationService(fresh_roots, DirectoryService(fresh_roots), QuickAccessStore(self.store.path), lambda: self.now)
        entry = fresh.state()["favorites"][0]; reopened = fresh.open(entry["id"])
        self.assertEqual(canonical_location(reopened["folder"]["path"]), canonical_location(path))

    def test_unavailable_favorite_is_reported_and_removable(self):
        path, folder = self.folder(); entry = self.service.toggle(folder["id"])["favorites"][0]; path.rmdir()
        self.assertFalse(self.service.state()["favorites"][0]["available"])
        with self.assertRaises(FileNotFoundError): self.service.open(entry["id"])
        self.assertEqual(self.service.remove(entry["id"])["favorites"], [])

    def test_store_concurrent_atomic_updates(self):
        threads = [threading.Thread(target=lambda: [self.store.update(lambda state: state.update(version=1)) for _ in range(20)]) for _ in range(8)]
        [thread.start() for thread in threads]; [thread.join() for thread in threads]
        self.assertEqual(json.loads(self.store.path.read_text())["version"], 1)
        self.assertFalse(list(self.base.glob("*.tmp")))

    def test_hot_frequency_and_recency_affect_ranking(self):
        old, _ = self.folder("old"); recent, _ = self.folder("recent")
        self.service.visit_path(old); self.now += 28 * 86400; self.service.visit_path(recent)
        self.assertEqual(self.service.state()["hot"][0]["name"], "recent")
        for _ in range(6): self.service.visit_path(old)
        self.assertEqual(self.service.state()["hot"][0]["name"], "old")

    def test_hot_history_is_bounded(self):
        for index in range(MAX_USAGE + 20): self.service.visit_path(self.base / f"folder-{index}")
        self.assertLessEqual(len(self.store.load()["usage"]), MAX_USAGE)

    def test_migrate_updates_favorite_descendants(self):
        root, metadata = self.folder(); child = root / "child"; child.mkdir(); child_meta = self.directories.metadata(child)
        self.service.toggle(child_meta["id"]); moved = self.base / "moved"; root.rename(moved); self.service.migrate(root, moved)
        self.assertEqual(self.service.state()["favorites"][0]["path"], canonical_location(moved / "child"))

    def test_file_operation_rename_migrates_favorite_descendant(self):
        root, metadata = self.folder(); child = root / "child"; child.mkdir()
        self.service.toggle(self.directories.metadata(child)["id"])
        operations = FileOperations(self.roots, self.directories, self.service.migrate)
        renamed = operations.rename(metadata["id"], "renamed")
        self.assertEqual(
            self.service.state()["favorites"][0]["path"],
            canonical_location(Path(renamed["path"]) / "child"),
        )

    def test_migrate_does_not_match_same_prefix_sibling(self):
        root, _ = self.folder("foo"); sibling, sibling_meta = self.folder("foobar")
        self.service.toggle(sibling_meta["id"])
        self.service.migrate(root, self.base / "renamed")
        self.assertEqual(self.service.state()["favorites"][0]["path"], canonical_location(sibling))

    def test_search_only_authorized_roots_and_result_limit(self):
        root, _ = self.folder(); outside, _ = self.folder("outside")
        for index in range(5): (root / f"match-{index}.txt").write_text("x")
        (outside / "match-secret.txt").write_text("x")
        # Use a fresh registry so 'outside' is not authorized.
        roots = RootRegistry(); directories = DirectoryService(roots); directories.select(str(root))
        result = NavigationSearch(roots, directories, result_limit=2).search("match")
        self.assertEqual(len(result["results"]), 2); self.assertTrue(result["truncated"])
        self.assertNotIn("secret", str(result))

    def test_search_does_not_traverse_symlinks(self):
        root, _ = self.folder(); outside = self.base / "private"; outside.mkdir(); (outside / "needle.txt").write_text("x")
        link = root / "linked"
        try: link.symlink_to(outside, target_is_directory=True)
        except OSError: self.skipTest("symlinks unavailable")
        self.assertEqual(NavigationSearch(self.roots, self.directories).search("needle")["results"], [])

    def test_stale_search_result_is_rejected(self):
        root, _ = self.folder(); target = root / "needle.txt"; target.write_text("old")
        search = NavigationSearch(self.roots, self.directories); token = search.search("needle")["results"][0]["id"]
        target.unlink(); target.mkdir()
        with self.assertRaises(PermissionError): search.activate(token)

    def test_unchanged_search_activation_does_not_add_root(self):
        root, _ = self.folder(); parent = root / "parent"; parent.mkdir(); (parent / "needle.txt").write_text("ok")
        search = NavigationSearch(self.roots, self.directories); roots_before = self.roots.authorized_roots()
        result = search.activate(search.search("needle")["results"][0]["id"])
        self.assertEqual(canonical_location(result["folder"]["path"]), canonical_location(parent))
        self.assertEqual(self.roots.authorized_roots(), roots_before)

    def test_search_activation_rejects_ancestor_symlink_escape_without_adding_root(self):
        root, _ = self.folder(); parent = root / "parent"; parent.mkdir(); (parent / "needle.txt").write_text("ok")
        search = NavigationSearch(self.roots, self.directories); token = search.search("needle")["results"][0]["id"]
        outside = self.base / "outside"; outside.mkdir(); moved = outside / "parent"; parent.rename(moved)
        try: parent.symlink_to(moved, target_is_directory=True)
        except OSError as error: self.skipTest(f"symlinks unavailable: {error}")
        roots_before = self.roots.authorized_roots()
        with self.assertRaises(PermissionError): search.activate(token)
        self.assertEqual(self.roots.authorized_roots(), roots_before)
        with self.assertRaises(PermissionError): self.roots.authorize_existing_descendant(moved)


if __name__ == "__main__": unittest.main()
