"""Local HTTP server for the NodeFileManager baseline."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HOST = "127.0.0.1"
PORT = 8000
FRONTEND_DIRECTORY = Path(__file__).resolve().parent.parent / "frontend"
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://{host}" for host in ALLOWED_HOSTS}


class NodeFileManagerHandler(SimpleHTTPRequestHandler):
    """Serve the fixed frontend directory and the small, explicit API."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIRECTORY), **kwargs)

    def _has_allowed_host(self) -> bool:
        return self.headers.get("Host", "").lower() in ALLOWED_HOSTS

    def _has_allowed_origin(self) -> bool:
        return self.headers.get("Origin", "").lower() in ALLOWED_ORIGINS

    def _validate_request(self, *, require_origin: bool = False) -> bool:
        """Enforce the localhost HTTP boundary before routing a request."""
        if not self._has_allowed_host():
            self.send_error(400, "Invalid Host header")
            return False
        if require_origin and not self._has_allowed_origin():
            self.send_error(403, "Origin is not allowed")
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if not self._validate_request():
            return

        if urlsplit(self.path).path == "/api/health":
            payload = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return

        super().do_GET()

    def _reject_unimplemented_state_change(self) -> None:
        """Protect the boundary even before state-changing routes exist."""
        if not self._validate_request(require_origin=True):
            return
        self.send_error(404, "API endpoint not found")

    do_POST = _reject_unimplemented_state_change
    do_PUT = _reject_unimplemented_state_change
    do_PATCH = _reject_unimplemented_state_change
    do_DELETE = _reject_unimplemented_state_change


def main() -> None:
    """Run the server on the loopback interface only."""
    server = ThreadingHTTPServer((HOST, PORT), NodeFileManagerHandler)
    print(f"NodeFileManager: http://{HOST}:{PORT}/")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NodeFileManager.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
