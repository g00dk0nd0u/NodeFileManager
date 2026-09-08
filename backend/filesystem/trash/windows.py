"""Minimal ctypes adapter for an opt-in Windows Recycle Bin prototype.

The cross-thread identity is an absolute PIDL copied into Python ``bytes``.
No COM interface pointer survives a call. Each public call initializes COM on
its calling thread, creates fresh ``IShellItem`` objects, and releases every
owned interface before ``CoUninitialize``.

This does *not* establish a production capability gate. ``FOFX_RECYCLEONDELETE``
is a request rather than a preflight guarantee: policy, a disabled/unavailable
Recycle Bin, network or removable drives, and sync-provider behavior may differ.
Even a local fixed drive cannot be promised recoverable before PostDeleteItem
returns a non-NULL ``psiNewlyCreated`` -- which is after mutation. Production
Delete therefore remains disabled for every path class pending a reliable gate.
"""

from __future__ import annotations

import ctypes
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from .model import TrashError, TrashNotRecoverable


HRESULT = ctypes.c_long
ULONG = ctypes.c_ulong
DWORD = ctypes.c_ulong
LPVOID = ctypes.c_void_p

S_OK = 0
S_FALSE = 1
COINIT_APARTMENTTHREADED = 0x2
CLSCTX_INPROC_SERVER = 0x1
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_NOERRORUI = 0x0400
FOFX_RECYCLEONDELETE = 0x00080000
FOFX_EARLYFAILURE = 0x00100000


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_text(cls, value: str) -> "GUID":
        raw = uuid.UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


IID_IUNKNOWN = GUID.from_text("00000000-0000-0000-C000-000000000046")
IID_ISHELL_ITEM = GUID.from_text("43826D1E-E718-42EE-BC55-A1E261C37BFE")
IID_IFILE_OPERATION = GUID.from_text("947AAB5F-0A5C-4C13-B4D6-4BF7836FC9F8")
IID_PROGRESS_SINK = GUID.from_text("04B0F1A7-9490-44BC-96E1-4296A31252E2")
CLSID_FILE_OPERATION = GUID.from_text("3AD05575-8857-4850-9277-11B85BDB8E09")


def _failed(hr: int) -> bool:
    return bool(hr & 0x80000000)


def _check(hr: int, operation: str) -> None:
    value = ctypes.c_uint32(hr).value
    if _failed(value):
        raise TrashError(f"{operation} failed with HRESULT 0x{value:08X}")


def _guid_equal(left: ctypes.POINTER(GUID), right: GUID) -> bool:
    return ctypes.string_at(left, ctypes.sizeof(GUID)) == bytes(right)


class _ComPointer:
    def __init__(self, pointer: int | None) -> None:
        if not pointer:
            raise TrashError("Native API returned a NULL COM interface")
        self.value = ctypes.c_void_p(pointer)

    def method(self, index: int, restype, *argtypes):
        table = ctypes.cast(
            self.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
        return prototype(table[index])

    def release(self) -> None:
        if self.value:
            self.method(2, ULONG)(self.value)
            self.value = ctypes.c_void_p()

    def __enter__(self) -> "_ComPointer":
        return self

    def __exit__(self, *_exc) -> None:
        self.release()


class _ProgressSink:
    """Call-scoped COM sink which clones PostDeleteItem's PIDL immediately."""

    def __init__(self, adapter: "WindowsRecycleBinAdapter") -> None:
        self.adapter = adapter
        self.ref_count = 1
        self.delete_hresult: int | None = None
        self.identity: bytes | None = None

        query = ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID))
        add_ref = ctypes.WINFUNCTYPE(ULONG, LPVOID)
        release = ctypes.WINFUNCTYPE(ULONG, LPVOID)
        simple = ctypes.WINFUNCTYPE(HRESULT, LPVOID)
        finish = ctypes.WINFUNCTYPE(HRESULT, LPVOID, HRESULT)
        pre_delete = ctypes.WINFUNCTYPE(HRESULT, LPVOID, DWORD, LPVOID)
        post_delete = ctypes.WINFUNCTYPE(HRESULT, LPVOID, DWORD, LPVOID, HRESULT, LPVOID)
        pre_rename = ctypes.WINFUNCTYPE(HRESULT, LPVOID, DWORD, LPVOID, ctypes.c_wchar_p)
        post_rename = ctypes.WINFUNCTYPE(
            HRESULT, LPVOID, DWORD, LPVOID, ctypes.c_wchar_p, HRESULT, LPVOID
        )
        pre_transfer = ctypes.WINFUNCTYPE(
            HRESULT, LPVOID, DWORD, LPVOID, LPVOID, ctypes.c_wchar_p
        )
        post_transfer = ctypes.WINFUNCTYPE(
            HRESULT, LPVOID, DWORD, LPVOID, LPVOID, ctypes.c_wchar_p, HRESULT, LPVOID
        )
        pre_new = ctypes.WINFUNCTYPE(HRESULT, LPVOID, DWORD, LPVOID, ctypes.c_wchar_p)
        post_new = ctypes.WINFUNCTYPE(
            HRESULT, LPVOID, DWORD, LPVOID, ctypes.c_wchar_p, ctypes.c_wchar_p,
            DWORD, HRESULT, LPVOID
        )

        self._callbacks = [
            query(self._query_interface), add_ref(self._add_ref), release(self._release),
            simple(self._ok), finish(self._ignore),
            pre_rename(self._ignore), post_rename(self._ignore),
            pre_transfer(self._ignore), post_transfer(self._ignore),
            pre_transfer(self._ignore), post_transfer(self._ignore),
            pre_delete(self._ignore),
            post_delete(self._post_delete),
            pre_new(self._ignore), post_new(self._ignore),
            ctypes.WINFUNCTYPE(HRESULT, LPVOID, ctypes.c_uint, ctypes.c_uint)(self._ignore_progress),
            simple(self._ok), simple(self._ok), simple(self._ok),
        ]
        self._vtable = (ctypes.c_void_p * len(self._callbacks))(
            *[ctypes.cast(callback, ctypes.c_void_p) for callback in self._callbacks]
        )
        self._instance = (ctypes.POINTER(ctypes.c_void_p) * 1)(
            ctypes.cast(self._vtable, ctypes.POINTER(ctypes.c_void_p))
        )

    @property
    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(self._instance, ctypes.c_void_p)

    def _query_interface(self, _this, iid, output) -> int:
        if _guid_equal(iid, IID_IUNKNOWN) or _guid_equal(iid, IID_PROGRESS_SINK):
            output[0] = self.pointer
            self.ref_count += 1
            return S_OK
        output[0] = None
        return ctypes.c_long(0x80004002).value  # E_NOINTERFACE

    def _add_ref(self, _this) -> int:
        self.ref_count += 1
        return self.ref_count

    def _release(self, _this) -> int:
        self.ref_count -= 1
        return self.ref_count

    def _ok(self, _this) -> int:
        return S_OK

    def _ignore(self, *_args) -> int:
        return S_OK

    def _ignore_progress(self, _this, _done, _total) -> int:
        return S_OK

    def _post_delete(self, _this, _flags, _item, hr_delete, newly_created) -> int:
        self.delete_hresult = ctypes.c_uint32(hr_delete).value
        if not _failed(self.delete_hresult) and newly_created:
            try:
                self.identity = self.adapter._pidl_bytes(newly_created)
            except TrashError:
                return ctypes.c_long(0x80004005).value  # E_FAIL
        return S_OK


class WindowsRecycleBinAdapter:
    """Native adapter intended only for disposable prototype tests."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("WindowsRecycleBinAdapter is available only on Windows")
        self.ole32 = ctypes.OleDLL("ole32")
        self.shell32 = ctypes.WinDLL("shell32")
        self.ole32.CoInitializeEx.argtypes = [LPVOID, DWORD]
        self.ole32.CoInitializeEx.restype = HRESULT
        self.ole32.CoCreateInstance.argtypes = [
            ctypes.POINTER(GUID), LPVOID, DWORD, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID)
        ]
        self.ole32.CoCreateInstance.restype = HRESULT
        self.ole32.CoTaskMemFree.argtypes = [LPVOID]
        self.ole32.CoTaskMemFree.restype = None
        self.shell32.SHCreateItemFromParsingName.argtypes = [
            ctypes.c_wchar_p, LPVOID, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID)
        ]
        self.shell32.SHCreateItemFromParsingName.restype = HRESULT
        self.shell32.SHGetIDListFromObject.argtypes = [LPVOID, ctypes.POINTER(LPVOID)]
        self.shell32.SHGetIDListFromObject.restype = HRESULT
        self.shell32.ILGetSize.argtypes = [LPVOID]
        self.shell32.ILGetSize.restype = ctypes.c_uint
        self.shell32.SHCreateItemFromIDList.argtypes = [
            LPVOID, ctypes.POINTER(GUID), ctypes.POINTER(LPVOID)
        ]
        self.shell32.SHCreateItemFromIDList.restype = HRESULT

    @contextmanager
    def _com(self):
        hr = self.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        _check(hr, "CoInitializeEx")
        try:
            yield
        finally:
            self.ole32.CoUninitialize()

    def _shell_item_for_path(self, path: Path) -> _ComPointer:
        output = LPVOID()
        hr = self.shell32.SHCreateItemFromParsingName(
            os.fspath(path), None, ctypes.byref(IID_ISHELL_ITEM), ctypes.byref(output)
        )
        _check(hr, "SHCreateItemFromParsingName")
        return _ComPointer(output.value)

    def _shell_item_for_pidl(self, identity: bytes) -> tuple[_ComPointer, object]:
        if len(identity) < 2 or identity[-2:] != b"\0\0":
            raise TrashError("Opaque recycled identity is invalid")
        buffer = ctypes.create_string_buffer(identity)
        output = LPVOID()
        hr = self.shell32.SHCreateItemFromIDList(
            ctypes.cast(buffer, LPVOID), ctypes.byref(IID_ISHELL_ITEM), ctypes.byref(output)
        )
        _check(hr, "SHCreateItemFromIDList")
        return _ComPointer(output.value), buffer

    def _pidl_bytes(self, shell_item: int) -> bytes:
        pidl = LPVOID()
        hr = self.shell32.SHGetIDListFromObject(shell_item, ctypes.byref(pidl))
        _check(hr, "SHGetIDListFromObject")
        if not pidl.value:
            raise TrashError("SHGetIDListFromObject returned NULL")
        try:
            size = self.shell32.ILGetSize(pidl)
            if size < 2:
                raise TrashError("Shell returned an invalid absolute PIDL")
            return ctypes.string_at(pidl, size)
        finally:
            self.ole32.CoTaskMemFree(pidl)

    def _file_operation(self) -> _ComPointer:
        output = LPVOID()
        hr = self.ole32.CoCreateInstance(
            ctypes.byref(CLSID_FILE_OPERATION), None, CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_IFILE_OPERATION), ctypes.byref(output)
        )
        _check(hr, "CoCreateInstance(IFileOperation)")
        operation = _ComPointer(output.value)
        flags = FOF_SILENT | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOFX_EARLYFAILURE
        try:
            _check(operation.method(5, HRESULT, DWORD)(operation.value, flags), "SetOperationFlags")
        except BaseException:
            operation.release()
            raise
        return operation

    @staticmethod
    def _perform(operation: _ComPointer) -> None:
        _check(operation.method(21, HRESULT)(operation.value), "PerformOperations")
        aborted = ctypes.c_int()
        _check(
            operation.method(22, HRESULT, ctypes.POINTER(ctypes.c_int))(
                operation.value, ctypes.byref(aborted)
            ),
            "GetAnyOperationsAborted",
        )
        if aborted.value:
            raise TrashError("The Shell aborted the file operation")

    def recycle(self, path: Path) -> bytes:
        with self._com(), self._shell_item_for_path(path) as item, self._file_operation() as operation:
            sink = _ProgressSink(self)
            flags = FOF_SILENT | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOFX_RECYCLEONDELETE | FOFX_EARLYFAILURE
            _check(operation.method(5, HRESULT, DWORD)(operation.value, flags), "SetOperationFlags")
            _check(
                operation.method(18, HRESULT, LPVOID, LPVOID)(
                    operation.value, item.value, sink.pointer
                ),
                "DeleteItem",
            )
            self._perform(operation)
            if sink.delete_hresult is None:
                raise TrashNotRecoverable("PostDeleteItem was not called")
            _check(sink.delete_hresult, "PostDeleteItem.hrDelete")
            if sink.identity is None:
                raise TrashNotRecoverable(
                    "PostDeleteItem returned NULL psiNewlyCreated; recoverability was not proved"
                )
            return sink.identity

    def restore(self, recycled_identity: bytes, parent: Path, name: str) -> None:
        with self._com():
            recycled, keepalive = self._shell_item_for_pidl(recycled_identity)
            with recycled, self._shell_item_for_path(parent) as destination, self._file_operation() as operation:
                _ = keepalive  # PIDL bytes must remain alive through MoveItem/PerformOperations.
                _check(
                    operation.method(14, HRESULT, LPVOID, LPVOID, ctypes.c_wchar_p, LPVOID)(
                        operation.value, recycled.value, destination.value, name, None
                    ),
                    "MoveItem",
                )
                self._perform(operation)
