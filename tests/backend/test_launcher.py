"""Focused tests for runtime paths and launcher collision decisions."""

from __future__ import annotations

import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import launcher, runtime_paths


class RuntimePathsTestCase(unittest.TestCase):
    def test_source_resources_resolve_to_repository(self) -> None:
        with patch.object(runtime_paths.sys, "frozen", False, create=True):
            self.assertEqual(runtime_paths.frontend_directory().name, "frontend")
            self.assertTrue((runtime_paths.frontend_directory() / "index.html").is_file())

    def test_packaged_resources_use_meipass(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime_paths.sys, "frozen", True, create=True), patch.object(runtime_paths.sys, "_MEIPASS", directory, create=True):
            self.assertEqual(runtime_paths.resource_directory(), Path(directory).resolve())

    def test_windows_user_data_and_logs_are_writable_locations(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime_paths.sys, "platform", "win32"), patch.dict(runtime_paths.os.environ, {"LOCALAPPDATA": directory}):
            self.assertEqual(runtime_paths.user_data_directory(), Path(directory) / "NodeFileManager")
            self.assertEqual(runtime_paths.log_directory(), Path(directory) / "NodeFileManager" / "logs")


class LauncherDecisionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("launcher-test")

    def test_health_identity_is_strict(self) -> None:
        self.assertTrue(launcher.is_nodefilemanager_health({"status": "ok", "app": "NodeFileManager", "apiVersion": 1}))
        self.assertFalse(launcher.is_nodefilemanager_health({"status": "ok"}))

    @patch("backend.launcher.configure_logging")
    @patch("backend.launcher.open_browser")
    @patch("backend.launcher.probe_health", return_value={"status": "ok", "app": "NodeFileManager", "apiVersion": 1})
    def test_existing_instance_is_reused(self, _probe, browser, logging_mock) -> None:
        logging_mock.return_value = self.logger
        self.assertEqual(launcher.run(), 0)
        browser.assert_called_once()

    @patch("backend.launcher.configure_logging")
    @patch("backend.launcher.port_is_open", return_value=True)
    @patch("backend.launcher.probe_health", return_value=None)
    def test_foreign_port_is_not_killed(self, _probe, _port, logging_mock) -> None:
        logging_mock.return_value = self.logger
        self.assertEqual(launcher.run(no_browser=True), 2)


if __name__ == "__main__":
    unittest.main()
