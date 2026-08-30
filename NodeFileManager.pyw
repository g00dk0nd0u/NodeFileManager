"""Console-less Windows source entry point for NodeFileManager."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
import traceback


REPOSITORY_ROOT = Path(__file__).resolve().parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

def fallback_log_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "NodeFileManager" / "logs" / "NodeFileManager.log"


def write_fallback_log(details: str, log_path: Path) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write("Unexpected desktop-source startup exception\n")
            log.write(details)
            if not details.endswith("\n"):
                log.write("\n")
    except OSError:
        # Failure reporting must never mask the original startup error.
        pass


def show_startup_error(log_path: Path) -> None:
    if sys.platform != "win32":
        return
    message = f"NodeFileManager could not start.\n\nSee the log for details:\n{log_path}"
    ctypes.windll.user32.MessageBoxW(None, message, "NodeFileManager startup failed", 0x10)


def main() -> int:
    log_path = fallback_log_path()
    launcher = None
    try:
        from backend import launcher

        result = launcher.run(desktop_source=True)
        if result:
            show_startup_error(log_path)
        return result
    except BaseException:
        details = traceback.format_exc()
        logged = False
        if launcher is not None:
            try:
                launcher.configure_logging(console=False).exception("Unexpected desktop-source startup exception")
                logged = True
            except BaseException:
                pass
        if not logged:
            write_fallback_log(details, log_path)
        show_startup_error(log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
