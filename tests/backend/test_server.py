"""Integration tests for the localhost HTTP boundary."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.filesystem import folder_picker
from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.roots import RootRegistry
from backend.server import HOST, HTTPServer, NodeFileManagerHandler
from backend.workspace.store import WorkspaceStore


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer((HOST, 0), NodeFileManagerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(
        self,
        method: str,
        path: str,
        *,
        host: str = "127.0.0.1:8000",
        origin: str | None = None,
        body: object | None = None,
    ) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection(HOST, self.server.server_port)
        headers = {"Host": host}
        if origin is not None:
            headers["Origin"] = origin
        payload = json.dumps(body).encode() if body is not None else None
        if payload is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def test_health_and_static_frontend_are_served(self) -> None:
        status, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<h1>NodeFileManager</h1>", body)

    def test_invalid_host_is_rejected(self) -> None:
        status, _ = self.request("GET", "/api/health", host="attacker.example")
        self.assertEqual(status, 400)

    def test_state_change_requires_allowed_origin(self) -> None:
        status, _ = self.request(
            "POST", "/api/future", origin="https://attacker.example"
        )
        self.assertEqual(status, 403)

        status, _ = self.request(
            "POST", "/api/future", origin="http://127.0.0.1:8000"
        )
        self.assertEqual(status, 404)

    def test_select_folder_api_uses_picker_and_cancellation_is_normal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(NodeFileManagerHandler, "picker", staticmethod(lambda: directory)):
                status, body = self.request("POST", "/api/folders/select", origin="http://127.0.0.1:8000", body={})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["folder"]["path"], str(Path(directory).resolve()))
        with patch.object(NodeFileManagerHandler, "picker", staticmethod(lambda: None)):
            status, body = self.request("POST", "/api/folders/select", origin="http://127.0.0.1:8000", body={})
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)["folder"])


class FilesystemAndWorkspaceTestCase(unittest.TestCase):
    def test_folder_picker_hides_and_always_destroys_root_on_cancel(self) -> None:
        root = MagicMock()
        tkinter = MagicMock()
        tkinter.Tk.return_value = root
        tkinter.TclError = RuntimeError
        filedialog = MagicMock()
        filedialog.askdirectory.return_value = ""
        with patch.object(
            folder_picker.importlib,
            "import_module",
            side_effect=[tkinter, filedialog],
        ):
            self.assertIsNone(folder_picker.select_folder())
        root.withdraw.assert_called_once_with()
        root.attributes.assert_called_once_with("-topmost", True)
        filedialog.askdirectory.assert_called_once_with(parent=root, mustexist=True)
        root.destroy.assert_called_once_with()

    def test_listing_and_authorization_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as selected, tempfile.TemporaryDirectory() as outside:
            child = Path(selected, "Child")
            child.mkdir()
            Path(selected, "ordinary.txt").write_text("ignored")
            roots = RootRegistry()
            service = DirectoryService(roots)
            root = service.select(selected)
            children = service.children(str(root["id"]))
            self.assertEqual([item["name"] for item in children], ["Child"])
            with self.assertRaises(PermissionError):
                roots.remember(Path(outside))
            with self.assertRaises(PermissionError):
                service.children("unknown-id")

    def test_workspace_round_trip_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "state", "workspace.json")
            store = WorkspaceStore(path)
            self.assertEqual(store.load()["roots"], [])
            state = {"version": 1, "roots": [{"path": "C:/Example"}], "nodes": {}, "viewport": {"x": 3, "y": 4, "zoom": 1.2}}
            store.save(state)
            self.assertEqual(store.load(), state)
            path.unlink()
            self.assertEqual(store.load()["nodes"], {})


if __name__ == "__main__":
    unittest.main()
