"""Integration tests for the localhost HTTP boundary."""

from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

from backend.filesystem import folder_picker
from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.roots import RootRegistry, folder_id
from backend.filesystem.folder_picker import FolderPickerUnavailable
from backend.server import ApplicationLifecycle, HOST, NodeFileManagerHandler, ThreadingHTTPServer
from backend.workspace.store import WorkspaceStore


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer((HOST, 0), NodeFileManagerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self) -> None:
        NodeFileManagerHandler.lifecycle = ApplicationLifecycle()
        NodeFileManagerHandler.application_server = None

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
        health = json.loads(body)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["app"], "NodeFileManager")
        self.assertEqual(health["apiVersion"], 1)
        self.assertIsInstance(health["version"], str)
        self.assertIs(health["packaged"], False)

        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<h1>NodeFileManager</h1>", body)

    def test_saved_materialized_node_is_restored_and_reauthorized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory, "root"); root.mkdir()
            child = root / "saved-node"; child.mkdir()
            store = WorkspaceStore(Path(directory, "workspace.json"))
            state = {
                "version": 1, "roots": [{"path": str(root)}],
                "nodes": {"saved": {"path": str(child)}},
                "viewport": {"x": 0, "y": 0, "zoom": 1},
            }
            store.save(state)
            roots = RootRegistry()
            directories = DirectoryService(roots)
            with patch.object(NodeFileManagerHandler, "workspace", store), patch.object(NodeFileManagerHandler, "roots", roots), patch.object(NodeFileManagerHandler, "directories", directories):
                status, body = self.request("GET", "/api/workspace")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["state"], state)
                self.assertEqual(roots.path_for(folder_id(child)), child.resolve())

    def test_packaged_quit_is_rejected_during_mutation(self) -> None:
        self.assertTrue(NodeFileManagerHandler.lifecycle.begin_mutation())
        try:
            with patch("backend.server.is_packaged", return_value=True):
                status, body = self.request("POST", "/api/application/quit", origin="http://127.0.0.1:8000", body={})
            self.assertEqual(status, 409)
            self.assertEqual(json.loads(body)["code"], "operation_in_progress")
        finally:
            NodeFileManagerHandler.lifecycle.end_mutation()

    def test_packaged_quit_is_accepted_when_idle(self) -> None:
        with patch("backend.server.is_packaged", return_value=True):
            status, body = self.request("POST", "/api/application/quit", origin="http://127.0.0.1:8000", body={})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["stopping"])
        self.assertFalse(NodeFileManagerHandler.lifecycle.begin_mutation())

    def test_source_quit_remains_rejected(self) -> None:
        status, body = self.request("POST", "/api/application/quit", origin="http://127.0.0.1:8000", body={})
        self.assertEqual(status, 409)
        self.assertIn("Ctrl+C", json.loads(body)["error"])

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

    def test_picker_failure_releases_lock_for_subsequent_request(self) -> None:
        with patch.object(
            NodeFileManagerHandler,
            "picker",
            staticmethod(lambda: (_ for _ in ()).throw(FolderPickerUnavailable("broken"))),
        ):
            status, body = self.request("POST", "/api/folders/select", origin="http://127.0.0.1:8000")
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["code"], "picker_failed")
        with patch.object(NodeFileManagerHandler, "picker", staticmethod(lambda: None)):
            status, _ = self.request("POST", "/api/folders/select", origin="http://127.0.0.1:8000")
        self.assertEqual(status, 200)

    def test_health_stays_responsive_and_second_picker_is_rejected(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def pending_picker() -> None:
            entered.set()
            release.wait(2)
            return None

        result = []
        with patch.object(NodeFileManagerHandler, "picker", staticmethod(pending_picker)):
            thread = threading.Thread(target=lambda: result.append(self.request(
                "POST", "/api/folders/select", origin="http://127.0.0.1:8000"
            )))
            thread.start()
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.request("GET", "/api/health")[0], 200)
            status, body = self.request("POST", "/api/folders/select", origin="http://127.0.0.1:8000")
            self.assertEqual(status, 409)
            self.assertEqual(json.loads(body)["code"], "picker_already_open")
            release.set()
            thread.join(2)
        self.assertEqual(result[0][0], 200)

    def test_preview_allows_only_authorized_whitelisted_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "image.png").write_bytes(b"png-data")
            Path(directory, "notes.txt").write_text("private")
            with patch.object(NodeFileManagerHandler, "picker", staticmethod(lambda: directory)):
                _, body = self.request("POST", "/api/folders/select", origin="http://127.0.0.1:8000", body={})
            root_id = json.loads(body)["folder"]["id"]
            _, body = self.request("GET", f"/api/folders/children?id={root_id}")
            files = {item["name"]: item for item in json.loads(body)["files"]}
            status, body = self.request("GET", f"/api/files/preview?id={files['image.png']['id']}")
            self.assertEqual((status, body), (200, b"png-data"))
            connection = http.client.HTTPConnection(HOST, self.server.server_port)
            connection.request("GET", f"/api/files/preview?id={files['image.png']['id']}", headers={"Host": "127.0.0.1:8000"})
            response = connection.getresponse(); self.assertEqual(response.getheader("Content-Type"), "image/png")
            self.assertEqual(response.getheader("Content-Disposition"), "inline"); response.read(); connection.close()
            self.assertEqual(self.request("GET", f"/api/files/preview?id={files['notes.txt']['id']}")[0], 403)
            self.assertEqual(self.request("GET", "/api/files/preview?id=unknown")[0], 403)


class FilesystemAndWorkspaceTestCase(unittest.TestCase):
    def picker_result(self, stdout: str, returncode: int = 0, stderr: str = "") -> object:
        return subprocess.CompletedProcess([], returncode, stdout, stderr)

    def test_folder_picker_selected_and_cancelled_protocol(self) -> None:
        with patch.object(folder_picker.subprocess, "run", return_value=self.picker_result(
            '{"status":"selected","path":"/example"}'
        )) as run:
            self.assertEqual(folder_picker.select_folder(), "/example")
            self.assertEqual(run.call_args.args[0][0], folder_picker.sys.executable)
            self.assertNotIn("shell", run.call_args.kwargs)
        with patch.object(folder_picker.subprocess, "run", return_value=self.picker_result(
            '{"status":"cancelled"}'
        )):
            self.assertIsNone(folder_picker.select_folder())

    def test_folder_picker_reports_child_error_crash_and_malformed_output(self) -> None:
        cases = [
            self.picker_result('{"status":"error","reason":"Tcl failed"}'),
            self.picker_result("", returncode=1, stderr="crash"),
            self.picker_result("not-json"),
            self.picker_result('{"status":"selected"}'),
        ]
        for completed in cases:
            with self.subTest(completed=completed), patch.object(
                folder_picker.subprocess, "run", return_value=completed
            ):
                with self.assertRaises(FolderPickerUnavailable):
                    folder_picker.select_folder()

    def test_folder_picker_timeout_is_clean_error(self) -> None:
        with patch.object(
            folder_picker.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["python"], 600),
        ) as run:
            with self.assertRaisesRegex(FolderPickerUnavailable, "タイムアウト"):
                folder_picker.select_folder()
        self.assertEqual(run.call_args.kwargs["timeout"], folder_picker.PICKER_TIMEOUT_SECONDS)

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

    def test_listing_is_one_lazy_scandir_and_one_parent_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as selected:
            child = Path(selected, "Child"); child.mkdir()
            Path(child, "deep").mkdir(); Path(selected, "ordinary.txt").write_text("file")
            roots = RootRegistry(); service = DirectoryService(roots); root = service.select(selected)
            original_resolve = Path.resolve
            with patch("backend.filesystem.directory_service.os.scandir", wraps=os.scandir) as scandir, patch.object(
                Path, "resolve", autospec=True,
                side_effect=lambda path, strict=False: original_resolve(path, strict=strict),
            ) as resolve:
                contents = service.contents(str(root["id"]))
            self.assertEqual(scandir.call_count, 1)
            self.assertEqual(resolve.call_count, 1)
            self.assertEqual(contents["folders"][0]["childrenState"], "unknown")

    def test_listed_symlink_is_registered_lexically_but_checked_before_use(self) -> None:
        with tempfile.TemporaryDirectory() as selected, tempfile.TemporaryDirectory() as outside:
            link = Path(selected, "outside-link")
            try:
                link.symlink_to(Path(outside), target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks unavailable: {error}")
            roots = RootRegistry(); service = DirectoryService(roots); root = service.select(selected)
            contents = service.contents(str(root["id"])); item = (contents["folders"] + contents["files"])[0]
            with self.assertRaises(PermissionError):
                roots.path_for(str(item["id"]))

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
