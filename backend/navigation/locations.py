"""Canonical filesystem-location identity for navigation persistence."""

from __future__ import annotations

import os
from pathlib import Path


def canonical_location(path: str | Path) -> str:
    """Return one absolute, platform-normalized form, including missing targets.

    Existing ancestors are resolved first so Windows short-name aliases and
    junction-backed parent spellings converge.  Missing trailing components
    are then appended lexically, which also works after a source was moved.
    """
    candidate = Path(path).absolute()
    missing: list[str] = []
    existing = candidate
    while not existing.exists():
        if existing.parent == existing:
            break
        missing.append(existing.name)
        existing = existing.parent
    try:
        normalized = existing.resolve(strict=True)
    except OSError:
        normalized = existing.resolve(strict=False)
    for component in reversed(missing):
        normalized /= component
    return os.path.normcase(os.path.normpath(str(normalized)))
