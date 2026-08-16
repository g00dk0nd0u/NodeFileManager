"""Local HTTP server for the NodeFileManager baseline."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HOST = "127.0.0.1"
PORT = 8000
FRONTEND_DIRECTORY = Path(__file__).resolve().parent.parent / "frontend"


class NodeFileManagerHandler(SimpleHTTPRequestHandler):
    """Serve the fixed frontend directory and the small, explicit API."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIRECTORY), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
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
