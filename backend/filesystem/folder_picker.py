"""Replaceable native folder selection boundary."""


class FolderPickerUnavailable(RuntimeError):
    """Raised when this Python installation has no Tk support."""


def select_folder() -> str | None:
    """Open a native directory chooser; cancellation returns ``None``."""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError as error:
        raise FolderPickerUnavailable(
            "この Python では tkinter を利用できないため、フォルダーを選択できません。"
        ) from error

    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        raise FolderPickerUnavailable(
            "フォルダー選択ダイアログを開始できません。Python の Tk 構成を確認してください。"
        ) from error
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(parent=root, mustexist=True)
        return selected or None
    finally:
        root.destroy()
