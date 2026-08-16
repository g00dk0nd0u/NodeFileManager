"""Read-only directory metadata exposed to the frontend."""

from pathlib import Path

from .roots import RootRegistry


class DirectoryService:
    def __init__(self, roots: RootRegistry) -> None:
        self.roots = roots

    @staticmethod
    def _has_children(path: Path) -> bool:
        try:
            return any(entry.is_dir() for entry in path.iterdir())
        except OSError:
            return False

    def metadata(self, path: Path, parent_id: str | None = None) -> dict[str, object]:
        identifier = self.roots.remember(path)
        return {
            "id": identifier,
            "name": path.name or str(path),
            "path": str(path),
            "parentId": parent_id,
            "hasChildren": self._has_children(path),
        }

    def select(self, path: str) -> dict[str, object]:
        return self.metadata(self.roots.authorize_root(path))

    def children(self, parent_id: str) -> list[dict[str, object]]:
        parent = self.roots.get(parent_id)
        children = []
        try:
            entries = sorted(
                (entry for entry in parent.iterdir() if entry.is_dir()),
                key=lambda entry: entry.name.casefold(),
            )
        except OSError as error:
            raise PermissionError(f"Folder cannot be read: {error}") from error
        for entry in entries:
            try:
                children.append(self.metadata(entry, parent_id))
            except OSError:
                continue
        return children
