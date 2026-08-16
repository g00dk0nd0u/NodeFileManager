"""Localhost-only HTTP server for NodeFileManager."""

from __future__ import annotations

import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from backend.filesystem import folder_picker
from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.folder_picker import FolderPickerUnavailable
from backend.filesystem.folder_browser import FolderBrowser
from backend.filesystem.opener import FileOpener
from backend.filesystem.operations import FileOperationError, FileOperations
from backend.filesystem.roots import RootRegistry
from backend.workspace.store import WorkspaceStore

HOST = "127.0.0.1"
PORT = 8000
FRONTEND_DIRECTORY = Path(__file__).resolve().parent.parent / "frontend"
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://{host}" for host in ALLOWED_HOSTS}


class NodeFileManagerHandler(SimpleHTTPRequestHandler):
    """Serve the frontend and explicit filesystem/workspace APIs."""

    roots = RootRegistry()
    directories = DirectoryService(roots)
    operations = FileOperations(roots, directories)
    folder_browser = FolderBrowser(directories)
    opener = FileOpener(roots)
    workspace = WorkspaceStore()
    picker = staticmethod(folder_picker.select_folder)
    picker_lock = threading.Lock()

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIRECTORY), **kwargs)

    def _json(self, status: int, value: object) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _has_allowed_host(self) -> bool:
        return self.headers.get("Host", "").lower() in ALLOWED_HOSTS

    def _has_allowed_origin(self) -> bool:
        return self.headers.get("Origin", "").lower() in ALLOWED_ORIGINS

    def _validate_request(self, *, require_origin: bool = False) -> bool:
        if not self._has_allowed_host():
            self.send_error(400, "Invalid Host header")
            return False
        if require_origin and not self._has_allowed_origin():
            self.send_error(403, "Origin is not allowed")
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if not self._validate_request():
            return
        request = urlsplit(self.path)
        if request.path == "/api/health":
            self._json(200, {"status": "ok"})
        elif request.path == "/api/folders/children":
            identifier = parse_qs(request.query).get("id", [""])[0]
            try:
                self._json(200, self.directories.contents(identifier))
            except (PermissionError, FileNotFoundError, NotADirectoryError) as error:
                self._json(403, {"error": str(error)})
        elif request.path == "/api/workspace":
            state = self.workspace.load()
            # Re-authorize only stored roots that still exist; inaccessible roots remain
            # in state so the UI can explain what was not restored.
            available = []
            for root in state.get("roots", []):
                try:
                    available.append(self.directories.select(str(root["path"])))
                except (OSError, KeyError, TypeError):
                    continue
            for node in state.get("nodes", {}).values():
                try:
                    self.roots.remember(Path(node["path"]))
                except (OSError, KeyError, TypeError, PermissionError):
                    continue
            self._json(200, {"state": state, "availableRoots": available})
        elif request.path.startswith("/api/"):
            self.send_error(404, "API endpoint not found")
        else:
            super().do_GET()

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request is too large")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def do_POST(self) -> None:  # noqa: N802
        if not self._validate_request(require_origin=True):
            return
        path = urlsplit(self.path).path
        if path.startswith("/api/folder-browser/"):
            try:
                body = self._read_json()
                if path.endswith("/start"):
                    result = self.folder_browser.start()
                elif path.endswith("/navigate"):
                    result = self.folder_browser.navigate(body.get("sessionId"), body.get("folderId"))
                elif path.endswith("/confirm"):
                    result = {"folder": self.folder_browser.confirm(body.get("sessionId"))}
                elif path.endswith("/cancel"):
                    self.folder_browser.cancel(body.get("sessionId")); result = {"cancelled": True}
                else:
                    self.send_error(404, "API endpoint not found"); return
                self._json(200, result)
            except (ValueError, OSError, PermissionError) as error:
                self._operation_error(error)
            return
        if path in {"/api/files/open", "/api/items/copy", "/api/items/move"}:
            try:
                body = self._read_json()
                identifier = str(body.get("id", ""))
                if path == "/api/files/open":
                    self.opener.open(identifier)
                    self._json(200, {"opened": True})
                else:
                    destination_id = str(body.get("destinationId", ""))
                    operation = self.operations.copy if path.endswith("copy") else self.operations.move
                    self._json(200, {"item": operation(identifier, destination_id)})
            except (ValueError, OSError, PermissionError) as error:
                self._operation_error(error)
            return
        if path != "/api/folders/select":
            self.send_error(404, "API endpoint not found")
            return
        if not self.picker_lock.acquire(blocking=False):
            self._json(409, {
                "error": "フォルダー選択ダイアログは既に開いています。",
                "code": "picker_already_open",
            })
            return
        try:
            try:
                selected = self.picker()
                folder = self.directories.select(selected) if selected else None
                self._json(200, {"folder": folder})
            except FolderPickerUnavailable as error:
                self._json(503, {"error": str(error), "code": "picker_failed"})
            except OSError as error:
                self._json(400, {"error": f"選択したフォルダーを利用できません: {error}"})
        finally:
            self.picker_lock.release()

    def do_PUT(self) -> None:  # noqa: N802
        if not self._validate_request(require_origin=True):
            return
        if urlsplit(self.path).path != "/api/workspace":
            self.send_error(404, "API endpoint not found")
            return
        try:
            state = self._read_json()
            self.workspace.save(state)
            self._json(200, {"saved": True})
        except (ValueError, json.JSONDecodeError, OSError) as error:
            self._json(400, {"error": str(error)})

    def do_PATCH(self) -> None:  # noqa: N802
        if not self._validate_request(require_origin=True):
            return
        if urlsplit(self.path).path != "/api/items/rename":
            self.send_error(404, "API endpoint not found")
            return
        try:
            body = self._read_json()
            item = self.operations.rename(str(body.get("id", "")), body.get("name"))
            self._json(200, {"item": item})
        except (ValueError, OSError, PermissionError) as error:
            self._operation_error(error)

    do_DELETE = lambda self: self._reject_state_change()  # noqa: E731

    def _operation_error(self, error: Exception) -> None:
        if isinstance(error, PermissionError):
            status = 403
        elif isinstance(error, FileNotFoundError):
            status = 404
        elif isinstance(error, FileExistsError):
            status = 409
        else:
            status = 400
        self._json(status, {"error": str(error)})

    def _reject_state_change(self) -> None:
        if self._validate_request(require_origin=True):
            self.send_error(404, "API endpoint not found")


def main() -> None:
    # The picker waits in one request thread; Tk itself lives in its child.
    server = ThreadingHTTPServer((HOST, PORT), NodeFileManagerHandler)
    print(f"NodeFileManager: http://{HOST}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NodeFileManager.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
