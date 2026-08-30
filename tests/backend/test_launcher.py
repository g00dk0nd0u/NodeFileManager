"""Focused tests for runtime paths and launcher collision decisions."""

from __future__ import annotations

import ast
import builtins
from importlib.machinery import SourceFileLoader
import importlib.util
import logging
from pathlib import Path
import py_compile
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

    @patch("backend.launcher.configure_logging")
    @patch("backend.launcher.create_server", side_effect=OSError("test bind failure"))
    @patch("backend.launcher.port_is_open", return_value=False)
    @patch("backend.launcher.probe_health", return_value=None)
    def test_desktop_source_enables_source_quit(self, _probe, _port, create, logging_mock) -> None:
        logging_mock.return_value = self.logger
        self.assertEqual(launcher.run(no_browser=True, desktop_source=True), 2)
        create.assert_called_once_with(enable_source_quit=True)
        logging_mock.assert_called_once_with(console=False)

    def load_windows_entry_point(self):
        entry_point = Path(__file__).resolve().parents[2] / "NodeFileManager.pyw"
        loader = SourceFileLoader("nodefilemanager_pyw_test", str(entry_point))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return entry_point, module

    def test_windows_source_entry_point_is_valid_and_delegates_to_launcher(self) -> None:
        entry_point, _module = self.load_windows_entry_point()
        py_compile.compile(str(entry_point), doraise=True)
        source = entry_point.read_text(encoding="utf-8")
        self.assertIn("from backend import launcher", source)
        self.assertIn("launcher.run(desktop_source=True)", source)
        self.assertNotIn("create_server", source)
        top_level_backend_imports = []
        for node in ast.parse(source).body:
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("backend"):
                top_level_backend_imports.append(node)
            elif isinstance(node, ast.Import) and any(alias.name.startswith("backend") for alias in node.names):
                top_level_backend_imports.append(node)
        self.assertEqual(top_level_backend_imports, [])

    def test_windows_entry_point_reports_backend_import_failure(self) -> None:
        _entry_point, module = self.load_windows_entry_point()
        real_import = builtins.__import__

        def fail_backend_import(name, *args, **kwargs):
            if name == "backend":
                raise ImportError("broken source checkout")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, patch.dict(module.os.environ, {"LOCALAPPDATA": directory}), patch.object(module, "show_startup_error") as show_error, patch.object(builtins, "__import__", side_effect=fail_backend_import):
            self.assertEqual(module.main(), 1)
            log_path = Path(directory) / "NodeFileManager" / "logs" / "NodeFileManager.log"
            show_error.assert_called_once_with(log_path)
            self.assertIn("broken source checkout", log_path.read_text(encoding="utf-8"))

    def test_windows_entry_point_logs_launcher_exception_and_reports_path(self) -> None:
        _entry_point, module = self.load_windows_entry_point()
        with tempfile.TemporaryDirectory() as directory, patch.dict(module.os.environ, {"LOCALAPPDATA": directory}), patch.object(launcher, "run", side_effect=RuntimeError("launcher failed")), patch.object(launcher, "configure_logging", side_effect=OSError("logging unavailable")), patch.object(module, "show_startup_error") as show_error:
            self.assertEqual(module.main(), 1)
            log_path = Path(directory) / "NodeFileManager" / "logs" / "NodeFileManager.log"
            show_error.assert_called_once_with(log_path)
            self.assertIn("launcher failed", log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
