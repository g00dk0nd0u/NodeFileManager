"""Favorites and deterministic recency-times-frequency HOT ranking."""

from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path

from backend.filesystem.directory_service import DirectoryService
from backend.filesystem.roots import RootRegistry
from .locations import canonical_location
from .store import MAX_USAGE, QuickAccessStore


def navigation_id(path: str | Path) -> str:
    return "nav_" + hashlib.sha256(canonical_location(path).encode()).hexdigest()[:24]


class NavigationService:
    def __init__(self, roots: RootRegistry, directories: DirectoryService, store: QuickAccessStore | None = None, clock=time.time) -> None:
        self.roots, self.directories, self.store, self.clock = roots, directories, store or QuickAccessStore(), clock
        self._favorite_paths: dict[str, str] = {}

    def _entry(self, item: dict[str, object], favorite: bool) -> dict[str, object]:
        path = Path(canonical_location(str(item["path"]))); available = path.is_dir()
        return {"id": navigation_id(path), "name": path.name or str(path),
                "path": str(path), "available": available, "favorite": favorite}

    def state(self, hot_limit: int = 8) -> dict[str, object]:
        state = self.store.load(); favorites = [self._entry(item, True) for item in state["favorites"]]
        excluded = {canonical_location(str(item["path"])) for item in state["favorites"]}
        now = self.clock(); ranked = []
        for item in state["usage"].values():
            if canonical_location(str(item["path"])) in excluded: continue
            age_days = max(0, now - float(item["lastUsed"])) / 86400
            score = math.log2(int(item["count"]) + 1) * math.exp(-age_days / 14)
            ranked.append((score, str(item["path"]), item))
        ranked.sort(key=lambda row: (-row[0], row[1].casefold()))
        return {"favorites": favorites, "hot": [self._entry(item, False) for _, _, item in ranked[:hot_limit]]}

    def toggle(self, authorized_id: str) -> dict[str, object]:
        path = self.roots.get(authorized_id)
        location = canonical_location(path); nav_id = navigation_id(location)
        def mutate(state):
            matches = [item for item in state["favorites"] if canonical_location(item["path"]) == location]
            if matches: state["favorites"] = [item for item in state["favorites"] if canonical_location(item["path"]) != location]
            else: state["favorites"].append({"id": nav_id, "path": location})
            return not matches
        favorite = self.store.update(mutate)
        self._favorite_paths[nav_id] = location
        return {"favorite": favorite, "favoriteId": nav_id, "favoriteName": path.name or str(path), **self.state()}

    def set_favorite(self, nav_id: str, favorite: bool) -> dict[str, object]:
        """Idempotently replay a session-known Favorite mutation."""
        state = self.store.load()
        item = next((item for item in state["favorites"] if navigation_id(item["path"]) == nav_id), None)
        location = canonical_location(item["path"]) if item else self._favorite_paths.get(nav_id)
        if location is None:
            raise PermissionError("Favorite entry is not available")
        self._favorite_paths[nav_id] = location
        def mutate(current):
            current["favorites"] = [entry for entry in current["favorites"] if navigation_id(entry["path"]) != nav_id]
            if favorite:
                current["favorites"].append({"id": nav_id, "path": location})
        self.store.update(mutate)
        path = Path(location)
        return {"favorite": favorite, "favoriteId": nav_id, "favoriteName": path.name or str(path), **self.state()}

    def remove(self, nav_id: str) -> dict[str, object]:
        return self.set_favorite(nav_id, False)

    def visit_path(self, path: Path) -> None:
        now = self.clock(); location = canonical_location(path); key = navigation_id(location)
        def mutate(state):
            current = state["usage"].get(key, {"path": location, "count": 0, "lastUsed": now})
            current.update(path=location, count=min(int(current["count"]) + 1, 1_000_000), lastUsed=now)
            state["usage"][key] = current
            if len(state["usage"]) > MAX_USAGE:
                keep = sorted(state["usage"], key=lambda ident: state["usage"][ident]["lastUsed"], reverse=True)[:MAX_USAGE]
                state["usage"] = {ident: state["usage"][ident] for ident in keep}
        self.store.update(mutate)

    def visit_authorized(self, identifier: str) -> dict[str, object]:
        path = self.roots.get(identifier); self.visit_path(path); return self.state()

    def open(self, nav_id: str) -> dict[str, object]:
        state = self.store.load(); candidates = list(state["favorites"]) + list(state["usage"].values())
        item = next((item for item in candidates if navigation_id(item["path"]) == nav_id), None)
        if item is None: raise PermissionError("Navigation entry is not available")
        path = Path(item["path"])
        if not path.is_dir(): raise FileNotFoundError("Favorite or HOT folder is unavailable")
        folder = self.directories.select(str(path)); self.visit_path(path)
        return {"folder": folder, **self.state()}

    def migrate(self, old: str | Path, new: str | Path) -> None:
        old_path, new_path = Path(canonical_location(old)), Path(canonical_location(new))
        def moved(value: str) -> str:
            path = Path(canonical_location(value))
            try:
                relative = path.relative_to(old_path)
            except ValueError:
                return canonical_location(path)
            return canonical_location(new_path / relative)
        def mutate(state):
            for item in state["favorites"]: item["path"] = moved(item["path"]); item["id"] = navigation_id(Path(item["path"]))
            rebuilt = {}
            for item in state["usage"].values(): item["path"] = moved(item["path"]); rebuilt[navigation_id(Path(item["path"]))] = item
            state["usage"] = rebuilt
        self.store.update(mutate)
