"""Replaceable native folder selection boundary."""

import importlib


class FolderPickerUnavailable(RuntimeError):
    """Raised when this Python installation has no Tk support."""


def select_folder() -> str | None:
    """Open a native directory chooser; cancellation returns ``None``."""
    try:
        tkinter = importlib.import_module("tkinter")
        filedialog = importlib.import_module("tkinter.filedialog")
    except ModuleNotFoundError as error:
        raise FolderPickerUnavailable(
            "この Python では tkinter を利用できないため、フォルダーを選択できません。"
        ) from error

    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        raise FolderPickerUnavailable(
            "フォルダー選択ダイアログを開始できません。Python の Tk 構成を確認してください。"
        ) from error
    try:
        root.withdraw()
        root.update_idletasks()
        try:
            root.attributes("-topmost", True)
            root.lift()
        except tkinter.TclError:
            # Window-manager hints are best effort across Tk platforms.
            pass
        selected = filedialog.askdirectory(parent=root, mustexist=True)
        return selected or None
    finally:
        root.destroy()
