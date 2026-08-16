"""Read-only directory metadata exposed to the frontend."""

from pathlib import Path

from .roots import RootRegistry


class DirectoryService:
    def __init__(self, roots: RootRegistry) -> None:
        self.roots = roots

    @staticmethod
    def _has_children(path: Path) -> bool:
        try:
            return any(path.iterdir())
        except OSError:
            return False

    def metadata(self, path: Path, parent_id: str | None = None) -> dict[str, object]:
        identifier = self.roots.remember(path)
        kind = "folder" if path.is_dir() else "file"
        return {
            "id": identifier,
            "name": path.name or str(path),
            "path": str(path),
            "parentId": parent_id,
            "kind": kind,
            "extension": path.suffix if kind == "file" else "",
            "hasChildren": self._has_children(path) if kind == "folder" else False,
        }

    def select(self, path: str) -> dict[str, object]:
        return self.metadata(self.roots.authorize_root(path))

    def contents(self, parent_id: str) -> dict[str, list[dict[str, object]]]:
        parent = self.roots.get(parent_id)
        folders, files = [], []
        try:
            entries = sorted(
                parent.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.casefold()),
            )
        except OSError as error:
            raise PermissionError(f"Folder cannot be read: {error}") from error
        for entry in entries:
            try:
                item = self.metadata(entry, parent_id)
                (folders if item["kind"] == "folder" else files).append(item)
            except OSError:
                continue
        return {"folders": folders, "files": files}

    def children(self, parent_id: str) -> list[dict[str, object]]:
        return self.contents(parent_id)["folders"]
