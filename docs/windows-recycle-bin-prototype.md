# Windows Recycle Bin replay prototype

This slice is deliberately disconnected from the application and accepts only
self-created data in its opt-in integration test. It uses `IFileOperation` with
`FOFX_RECYCLEONDELETE`, captures `PostDeleteItem.psiNewlyCreated`, converts that
object to an absolute PIDL, and copies the PIDL into Python-owned bytes. A later
thread initializes its own COM apartment and recreates an `IShellItem` with
`SHCreateItemFromIDList`; no raw COM pointer crosses calls or threads.

Undo moves that exact item to its original parent and name only when the target
is free. Redo verifies the restored object, recycles that path, and replaces the
old receipt identity with the new PIDL. It never enumerates or searches the
Recycle Bin by display name.

## Capability finding

Windows offers no reliable pre-mutation guarantee that a requested delete will
produce a recoverable object. `FOFX_RECYCLEONDELETE` expresses intent, while the
decisive evidence (`PostDeleteItem` success and non-NULL `psiNewlyCreated`)
arrives after the operation. Availability can vary with Recycle Bin settings
and policy, and with local fixed, removable, network, and sync-provider paths.
Volume type alone is therefore not a sufficient gate. No path class is enabled
for production by this prototype.

A production Delete remains blocked until it can refuse the operation *before*
mutation whenever recoverability is uncertain. The native replay mechanism may
work on tested local environments while that capability problem remains
unsolved.
