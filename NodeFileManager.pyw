"""Console-less Windows source entry point for NodeFileManager."""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend import launcher  # noqa: E402
from backend.runtime_paths import log_directory  # noqa: E402


def show_startup_error() -> None:
    if sys.platform != "win32":
        return
    log_path = log_directory() / "NodeFileManager.log"
    message = f"NodeFileManager could not start.\n\nSee the log for details:\n{log_path}"
    ctypes.windll.user32.MessageBoxW(None, message, "NodeFileManager startup failed", 0x10)


def main() -> int:
    try:
        result = launcher.run(desktop_source=True)
        if result:
            show_startup_error()
        return result
    except BaseException:
        launcher.configure_logging(console=False).exception("Unexpected desktop-source startup exception")
        show_startup_error()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
