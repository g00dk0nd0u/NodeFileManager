"""Shared source and packaged launcher for the NodeFileManager lifecycle."""

from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import platform
import socket
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import webbrowser

from backend.runtime_paths import is_packaged, log_directory
from backend.server import HOST, PORT, create_server
from backend.version import BUILD_COMMIT, VERSION

URL = f"http://{HOST}:{PORT}/"
HEALTH_URL = f"{URL}api/health"


def configure_logging(*, console: bool = True) -> logging.Logger:
    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nodefilemanager")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(directory / "NodeFileManager.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        if not is_packaged() and console:
            logger.addHandler(logging.StreamHandler())
    return logger


def probe_health(timeout: float = 1.0) -> dict[str, object] | None:
    try:
        request = Request(HEALTH_URL, headers={"Host": f"{HOST}:{PORT}"})
        with urlopen(request, timeout=timeout) as response:
            value = json.load(response)
        return value if isinstance(value, dict) else None
    except (OSError, HTTPError, URLError, ValueError, json.JSONDecodeError):
        return None


def is_nodefilemanager_health(value: object) -> bool:
    return isinstance(value, dict) and value.get("status") == "ok" and value.get("app") == "NodeFileManager" and value.get("apiVersion") == 1


def port_is_open(timeout: float = 0.3) -> bool:
    with socket.socket() as connection:
        connection.settimeout(timeout)
        return connection.connect_ex((HOST, PORT)) == 0


def open_browser(logger: logging.Logger) -> None:
    logger.info("Browser launch attempt: %s", URL)
    webbrowser.open(URL, new=0)


def run(*, no_browser: bool = False, desktop_source: bool = False) -> int:
    logger = configure_logging(console=not desktop_source)
    mode = "packaged" if is_packaged() else "desktop-source" if desktop_source else "source"
    logger.info("Application start mode=%s version=%s commit=%s python=%s bind=%s:%s", mode, VERSION, BUILD_COMMIT, platform.python_version(), HOST, PORT)
    health = probe_health()
    if is_nodefilemanager_health(health):
        logger.info("Duplicate-instance reuse")
        print("NodeFileManager is already running; reusing the existing instance.")
        if not no_browser:
            open_browser(logger)
        return 0
    if port_is_open():
        logger.error("Startup failure: port %s is occupied by another process", PORT)
        print(f"Error: port {PORT} is occupied by another process.", file=sys.stderr)
        return 2

    try:
        server = create_server(enable_source_quit=desktop_source)
    except OSError as error:
        logger.exception("Startup failure while binding port %s", PORT)
        print(f"Error: cannot start on port {PORT}: {error}", file=sys.stderr)
        return 2
    thread = threading.Thread(target=server.serve_forever, name="http-server", daemon=True)
    thread.start()
    try:
        for _ in range(50):
            if is_nodefilemanager_health(probe_health()):
                break
            if not thread.is_alive():
                raise RuntimeError("HTTP server stopped during startup")
            time.sleep(0.1)
        else:
            raise RuntimeError("health check timed out")
        logger.info("Health startup success")
        print(f"NodeFileManager is ready: {URL}")
        if not no_browser:
            open_browser(logger)
        while thread.is_alive():
            thread.join(0.5)
        logger.info("Clean shutdown")
        return 0
    except KeyboardInterrupt:
        logger.info("Clean shutdown requested by Ctrl+C")
        server.shutdown()
        thread.join(5)
        return 0
    except Exception:
        logger.exception("Unexpected launcher exception")
        server.shutdown()
        thread.join(5)
        return 1
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch NodeFileManager")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser (for smoke tests)")
    return run(no_browser=parser.parse_args().no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
