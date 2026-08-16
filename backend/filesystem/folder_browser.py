"""Short-lived, opaque-ID sessions for the in-app folder chooser."""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from threading import RLock

from .directory_service import DirectoryService


class FolderBrowser:
    def __init__(self, directories: DirectoryService, ttl_seconds: int = 900) -> None:
        self.directories, self.ttl_seconds = directories, ttl_seconds
        self._sessions: dict[str, dict[str, object]] = {}
        self._lock = RLock()

    def _locations(self) -> list[Path]:
        locations = [Path.home()]
        if os.name == "nt":
            locations.extend(Path(drive) for drive in getattr(os, "listdrives", lambda: [])())
        else:
            locations.append(Path("/"))
            volumes = Path("/Volumes")
            if volumes.is_dir():
                locations.extend(path for path in volumes.iterdir() if path.is_dir())
        return list(dict.fromkeys(path.resolve() for path in locations if path.exists()))

    def _session(self, session_id: object) -> dict[str, object]:
        if not isinstance(session_id, str):
            raise PermissionError("Folder browser session is invalid")
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or time.monotonic() - float(session["touched"]) > self.ttl_seconds:
                self._sessions.pop(session_id, None)
                raise PermissionError("Folder browser session expired")
            session["touched"] = time.monotonic()
            return session

    @staticmethod
    def _token(paths: dict[str, Path], path: Path) -> str:
        token = secrets.token_urlsafe(18); paths[token] = path
        return token

    def _view(self, session: dict[str, object]) -> dict[str, object]:
        current = Path(session["current"]); paths: dict[str, Path] = session["paths"]  # type: ignore[assignment]
        paths.clear()
        folders = []
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        folders.append({"id": self._token(paths, current / entry.name), "name": entry.name})
        except OSError as error:
            raise PermissionError(f"Folder cannot be read: {error}") from error
        folders.sort(key=lambda item: str(item["name"]).casefold())
        parent = current.parent if current.parent != current else None
        parent_id = self._token(paths, parent) if parent else None
        locations = [{"id": self._token(paths, path), "name": "Home" if path == Path.home().resolve() else str(path)} for path in self._locations()]
        return {"sessionId": session["id"], "current": {"name": current.name or str(current), "path": str(current)}, "folders": folders, "parentId": parent_id, "locations": locations}

    def start(self) -> dict[str, object]:
        identifier = secrets.token_urlsafe(24)
        session = {"id": identifier, "current": Path.home().resolve(strict=True), "paths": {}, "touched": time.monotonic()}
        with self._lock:
            now = time.monotonic()
            self._sessions = {key: value for key, value in self._sessions.items() if now - float(value["touched"]) <= self.ttl_seconds}
            self._sessions[identifier] = session
        return self._view(session)

    def navigate(self, session_id: object, folder_id: object) -> dict[str, object]:
        session = self._session(session_id); paths: dict[str, Path] = session["paths"]  # type: ignore[assignment]
        if not isinstance(folder_id, str) or folder_id not in paths:
            raise PermissionError("Folder was not issued by this browser session")
        target = paths[folder_id].resolve(strict=True)
        if not target.is_dir(): raise NotADirectoryError(target)
        session["current"] = target
        return self._view(session)

    def confirm(self, session_id: object) -> dict[str, object]:
        session = self._session(session_id); current = Path(session["current"])
        self.cancel(session_id)
        return self.directories.select(str(current))

    def cancel(self, session_id: object) -> None:
        if isinstance(session_id, str):
            with self._lock: self._sessions.pop(session_id, None)
