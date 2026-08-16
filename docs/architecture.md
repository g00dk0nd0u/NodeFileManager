# Architecture

The application will keep three responsibilities separate as it grows. The initial skeleton defines only their boundaries; it does not implement domain services or state abstractions yet.

## Canvas

Owns visual node, edge, selection, and viewport state. It renders the graph and handles canvas interactions, but does not directly mutate the operating system filesystem.

## Workspace

Owns the user's layout and persistent workspace state. It will connect filesystem identities to saved node positions and other workspace preferences without redefining the filesystem hierarchy.

## Filesystem

Owns actual operating system filesystem operations. It will expose carefully scoped Rust-backed operations such as reading directories and, in later phases, rename, move, copy, and delete.

Keeping these boundaries separate allows visual layout changes to remain independent from real filesystem changes while avoiding premature implementation details.

