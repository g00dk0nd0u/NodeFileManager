"""Open authorized files with the operating system's default application."""

from __future__ import annotations

import os
import subprocess
import sys

from .roots import RootRegistry


class FileOpener:
    def __init__(self, roots: RootRegistry) -> None:
        self.roots = roots

    def open(self, identifier: str) -> None:
        target = self.roots.path_for(identifier)
        if not target.is_file():
            raise IsADirectoryError("Only files can be opened")
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["/usr/bin/open", str(target)], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", str(target)], close_fds=True)
