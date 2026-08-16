# -*- mode: python ; coding: utf-8 -*-
"""Reviewable one-folder Windows / macOS PyInstaller definition."""

import os
import sys

project = os.path.abspath(SPECPATH)
a = Analysis(
    [os.path.join(project, "scripts", "standalone_entry.py")],
    pathex=[project],
    binaries=[],
    datas=[(os.path.join(project, "frontend"), "frontend")],
    hiddenimports=[],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["tkinter"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="NodeFileManager",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="NodeFileManager")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="NodeFileManager.app", bundle_identifier="com.nodefilemanager.app", info_plist={"NSHighResolutionCapable": True})
