"""Build and archive the native-platform one-folder test application."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller is missing. Run: python -m pip install -r requirements-build.txt", file=sys.stderr)
        return 2
    build = ROOT / "build"
    dist = ROOT / "dist"
    for target in (build, dist):
        if target.exists():
            shutil.rmtree(target)
    build_info = ROOT / "backend" / "build_info.py"
    original_build_info = build_info.read_text(encoding="utf-8")
    commit = os.environ.get("NODEFILEMANAGER_BUILD_COMMIT", "").strip()
    try:
        if commit:
            build_info.write_text(f'"""Generated standalone build identity."""\n\nBUILD_COMMIT = {commit!r}\n', encoding="utf-8")
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(ROOT / "NodeFileManager.spec")], cwd=ROOT, check=True)
    finally:
        build_info.write_text(original_build_info, encoding="utf-8")
    machine = platform.machine().lower()
    architecture = "x64" if machine in {"amd64", "x86_64"} else "arm64" if machine in {"arm64", "aarch64"} else machine
    if sys.platform == "win32":
        source, stem = dist / "NodeFileManager", f"NodeFileManager-windows-{architecture}"
    elif sys.platform == "darwin":
        source, stem = dist / "NodeFileManager.app", f"NodeFileManager-macos-{architecture}"
    else:
        print("Standalone artifacts are currently supported on Windows and macOS only.", file=sys.stderr)
        return 2
    if sys.platform == "darwin":
        archive = str(dist / f"{stem}.zip")
        subprocess.run([
            "/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
            str(source), archive,
        ], check=True)
    else:
        archive = shutil.make_archive(str(dist / stem), "zip", root_dir=source.parent, base_dir=source.name)
    print(f"Standalone artifact: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
