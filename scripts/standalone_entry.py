"""Minimal PyInstaller entry point; all lifecycle behavior stays in launcher."""

from backend.launcher import main


if __name__ == "__main__":
    raise SystemExit(main())
