"""Integration tests for the localhost HTTP boundary."""

from __future__ import annotations

import http.client
import json
import threading
import unittest

from backend.server import HOST, NodeFileManagerHandler, ThreadingHTTPServer


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

    def request(
        self,
        method: str,
        path: str,
        *,
        host: str = "127.0.0.1:8000",
        origin: str | None = None,
    ) -> tuple[int, bytes]:
        connection = http.client.HTTPConnection(HOST, self.server.server_port)
        headers = {"Host": host}
        if origin is not None:
            headers["Origin"] = origin
        connection.request(method, path, headers=headers)
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


if __name__ == "__main__":
    unittest.main()
