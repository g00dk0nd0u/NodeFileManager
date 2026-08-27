# NodeFileManager — Claude project context

## Product intent

NodeFileManager is a persistent spatial workspace for active folders. It is intentionally **not** a conventional Windows Explorer clone and should not be redesigned into a tree-first file manager.

The core mental model is: keep only the folders relevant to current work materialized on a persistent spatial desk.

## Core UI concepts

- **Folder Panel**: a working window for one folder, not a lightweight processing node.
- **Working Set**: a spatial group of related materialized Folder Panels. A Working Set may contain multiple independent visual roots.
- **Compact Parent**: an upstream navigation tab for the real filesystem parent when that parent is not currently materialized. It is not a real hierarchy connector.
- **Trail**: one direct child is placed to the right of its parent.
- **Shelf**: multiple direct children are placed below the parent.
- **Connectors**: originate from the exact folder row and represent currently materialized visual parent/child relationships.
- **Isolate / Reattach**: a branch can leave a Working Set while preserving its descendants, then dock back when the required parent exists.
- **Filesystem Move**: dragging a file or folder into the corresponding file/folder region performs a real filesystem move. This must stay clearly distinct from spatial navigation.

## Current visual direction

Aim for a calm professional desktop tool:

- spatial clarity similar to Figma frames
- canvas interaction inspired by Blender-style spatial tools
- information density closer to VS Code / professional desktop software

Avoid turning the UI into:

- a generic web dashboard
- a game UI
- a shader/dataflow node editor
- a conventional folder tree

## Important design invariants

Unless a task explicitly requests otherwise, preserve:

- Folder Panel widths: approximately 330px single-column / 430px mixed file+folder
- about 10–12 useful visible rows with internal scrolling
- files on the left and folders on the right when both exist
- Trail = one child to the right
- Shelf = multiple children below
- branch-based layout that keeps descendant branches clear of ancestors
- neutral, visually secondary connectors
- amber family for selection/open state and blue for drag/drop targets
- Compact Parent as an upstream tab, visually separate from real connectors
- Working Set context derived from the current materialized visual-root structure, not from a guessed project name
- no permanently visible filesystem paths in the main UI

## Architecture / implementation constraints

Runtime is Python + vanilla HTML/CSS/JavaScript.

Do not introduce unless explicitly requested:

- React
- TypeScript
- npm runtime dependencies
- a frontend build step
- framework migration

The application must remain usable in environments where npm cannot be installed.

Key UI files:

- `frontend/css/canvas.css`
- `frontend/js/canvas/canvas.js`
- `frontend/js/canvas/node.js`
- `frontend/js/canvas/layout.js`
- `frontend/js/app.js`

Backend lives under `backend/`.

## Review priorities

For UI/UX review, evaluate both visual quality and daily usability. Pay particular attention to:

1. hierarchy readability with deep structures and many siblings
2. usability with 3–5 Working Sets and 10+ visible Folder Panels
3. long filenames and information density
4. connector readability without visual noise
5. clarity of selected / open / hover / drop states
6. discoverability of Compact Parent, search, Isolate, and Reattach
7. accidental filesystem Move risk
8. distinction between spatial navigation and destructive/mutating filesystem actions
9. Working Set grouping and identity
10. horizontal growth of long single-child Trails

Do not recommend broad redesigns before checking whether a focused change can solve the issue.

## Testing

Run at minimum:

```bash
python -m unittest discover -s tests/backend
python -m unittest discover -s tests/frontend
git diff --check
```

Use existing JavaScript syntax checks when available. Do not install npm merely to run tests.

## Working style

- Inspect the current latest branch/code before making claims.
- Separate confirmed code-based findings from speculative rendered-UI judgments.
- For design-review-only tasks, do not modify files.
- Keep changes narrowly scoped to the requested responsibility.
- Do not merge a PR unless explicitly instructed.
