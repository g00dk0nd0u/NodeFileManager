"""Security and lifecycle tests for the in-app folder-browser sessions."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.folder_browser import FolderBrowser
from backend.filesystem.roots import RootRegistry


class FolderBrowserTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.home = Path(self.temporary.name)
        self.child = self.home / "Chosen"; self.child.mkdir()
        self.roots = RootRegistry(); self.directories = DirectoryService(self.roots)
        self.browser = FolderBrowser(self.directories)
        self.home_patch = patch.object(Path, "home", return_value=self.home); self.home_patch.start()

    def tearDown(self):
        self.home_patch.stop(); self.temporary.cleanup()

    def test_navigation_accepts_only_server_issued_ids(self):
        view = self.browser.start()
        with self.assertRaises(PermissionError):
            self.browser.navigate(view["sessionId"], str(self.child))
        child_id = view["folders"][0]["id"]
        navigated = self.browser.navigate(view["sessionId"], child_id)
        self.assertEqual(navigated["current"]["path"], str(self.child.resolve()))

    def test_cancel_and_repeated_start_do_not_leave_stuck_session(self):
        first = self.browser.start(); self.browser.cancel(first["sessionId"])
        with self.assertRaises(PermissionError):
            self.browser.navigate(first["sessionId"], "anything")
        second = self.browser.start()
        self.assertNotEqual(first["sessionId"], second["sessionId"])

    def test_confirm_authorizes_exactly_current_folder_and_consumes_session(self):
        view = self.browser.start(); child_id = view["folders"][0]["id"]
        current = self.browser.navigate(view["sessionId"], child_id)
        folder = self.browser.confirm(view["sessionId"])
        self.assertEqual(folder["path"], current["current"]["path"])
        self.assertEqual(self.roots.get(str(folder["id"])), self.child.resolve())
        with self.assertRaises(PermissionError):
            self.browser.confirm(view["sessionId"])


if __name__ == "__main__": unittest.main()
