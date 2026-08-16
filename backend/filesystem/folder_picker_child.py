"""One-shot native folder chooser process; communicate only through JSON."""

from __future__ import annotations

import json
import sys


def pick() -> dict[str, str]:
    """Create one Tk interpreter, show one chooser, and return its result."""
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    try:
        root.withdraw()
        try:
            root.attributes("-topmost", True)
            root.lift()
            root.update_idletasks()
            root.update()
        except tkinter.TclError:
            pass
        selected = filedialog.askdirectory(parent=root, mustexist=True)
        if selected:
            return {"status": "selected", "path": selected}
        return {"status": "cancelled"}
    finally:
        try:
            root.attributes("-topmost", False)
        except tkinter.TclError:
            pass
        root.destroy()


def main() -> None:
    try:
        result = pick()
    except Exception as error:  # The parent receives errors via the protocol.
        result = {"status": "error", "reason": str(error) or type(error).__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
