"""Bounded name-only traversal of explicitly authorized roots."""

from __future__ import annotations

import os
import secrets
import threading
import time
from pathlib import Path

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.roots import RootRegistry

class NavigationSearch:
    def __init__(self, roots: RootRegistry, directories: DirectoryService, *, result_limit=50, scan_limit=10_000, time_limit=.35) -> None:
        self.roots, self.directories = roots, directories
        self.result_limit, self.scan_limit, self.time_limit = result_limit, scan_limit, time_limit
        self._tokens, self._lock = {}, threading.RLock()

    @staticmethod
    def _linked(path: Path) -> bool:
        junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(junction and junction())

    def search(self, query: str) -> dict[str, object]:
        query = query.strip().casefold()
        if len(query) < 2: raise ValueError("Search query must contain at least 2 characters")
        started = time.monotonic(); results, stack, scanned, truncated = [], list(self.roots.authorized_roots()), 0, False
        while stack:
            folder = stack.pop()
            try: entries = os.scandir(folder)
            except OSError: continue
            with entries:
                for entry in entries:
                    scanned += 1
                    if scanned > self.scan_limit or time.monotonic() - started > self.time_limit: truncated = True; stack.clear(); break
                    path = Path(entry.path)
                    if self._linked(path): continue
                    try: is_folder = entry.is_dir(follow_symlinks=False)
                    except OSError: continue
                    if is_folder: stack.append(path)
                    if query not in entry.name.casefold(): continue
                    try: signature = (entry.stat(follow_symlinks=False).st_dev, entry.stat(follow_symlinks=False).st_ino, is_folder)
                    except OSError: continue
                    token = secrets.token_urlsafe(18)
                    with self._lock: self._tokens[token] = (path, signature)
                    results.append({"id": token, "name": entry.name, "kind": "folder" if is_folder else "file", "context": str(path.parent)})
                    if len(results) >= self.result_limit: truncated = True; stack.clear(); break
        with self._lock:
            if len(self._tokens) > 1000: self._tokens = dict(list(self._tokens.items())[-500:])
        return {"results": results, "truncated": truncated, "scanned": scanned}

    def activate(self, token: str) -> dict[str, object]:
        with self._lock: saved = self._tokens.pop(token, None)
        if saved is None: raise PermissionError("Search result is stale or unauthorized")
        path, signature = saved
        try: stat = path.stat(follow_symlinks=False); current = (stat.st_dev, stat.st_ino, path.is_dir())
        except OSError as error: raise FileNotFoundError("Search result is stale") from error
        if current != signature or self._linked(path): raise PermissionError("Search result is stale or unsafe")
        parent = path if path.is_dir() else path.parent
        folder = self.directories.select(str(parent))
        item_id = None if path.is_dir() else self.roots.remember(path)
        return {"folder": folder, "fileId": item_id}
