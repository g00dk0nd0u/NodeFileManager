# NodeFileManager

NodeFileManager is a desktop file manager concept that will represent real folders and files as nodes on a free-form canvas.

This repository currently contains only the initial Tauri 2, React, TypeScript, and Vite project skeleton. Filesystem operations and the node canvas are intentionally not implemented yet.

## Prerequisites

- Node.js and npm
- Rust stable toolchain
- Platform requirements for [Tauri 2](https://v2.tauri.app/start/prerequisites/)

## Development

```sh
npm install
npm run tauri dev
```

## Validation

```sh
npm run typecheck
npm run build
npm run tauri build
```

## Project structure

- `src/app`: application entry UI
- `src/canvas`: future canvas state and rendering
- `src/workspace`: future workspace layout and persistence
- `src/filesystem`: future filesystem boundary
- `src/features`: future user-facing feature modules
- `src/components`: future shared UI components
- `src/utils`: future shared utilities
- `src-tauri`: Tauri configuration and Rust backend
- `docs`: product concept, architecture, and roadmap
- `tests`: future cross-cutting tests

