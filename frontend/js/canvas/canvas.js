import { createNodeElement, updateNodeElement } from "./node.js";
import { renderEdges } from "./edge.js";
import { applyViewport } from "./viewport.js";
import { childPositions } from "./layout.js";

export class FolderCanvas {
  constructor(element, onChange, loadChildren) {
    this.canvas = element; this.world = element.querySelector("#world"); this.edges = element.querySelector("#edges g");
    this.nodes = new Map(); this.elements = new Map(); this.viewport = { x: 0, y: 0, zoom: 1 };
    this.selected = null; this.selectedItem = null; this.onChange = onChange; this.loadChildren = loadChildren;
    this.actions = {}; this.dragSession = null;
    this.canvas.addEventListener("pointerdown", (event) => this.startPan(event));
    this.canvas.addEventListener("wheel", (event) => this.zoom(event), { passive: false });
    window.addEventListener("pointermove", (event) => this.continueDrag(event));
    window.addEventListener("pointerup", (event) => this.endDrag(event));
    window.addEventListener("pointercancel", (event) => this.cancelDrag(event));
    window.addEventListener("blur", () => this.finishDrag(false));
    this.canvas.addEventListener("lostpointercapture", (event) => this.cancelDrag(event), true);
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") this.escape(event); });
  }

  async restore(state, availableRoots) {
    this.viewport = { x: 0, y: 0, zoom: 1, ...(state.viewport || {}) };
    const savedNodes = state.nodes || {};
    this.nodes.clear();
    for (const [index, root] of availableRoots.entries()) {
      const saved = savedNodes[root.id];
      this.nodes.set(root.id, {
        ...root,
        x: saved?.x ?? index * 220,
        y: saved?.y ?? 80,
        expanded: saved?.expanded ?? true,
        childrenLoaded: false,
      });
    }
    this.render();
    for (const root of availableRoots) await this.restoreExpanded(root.id, savedNodes);
    this.render();
    this.changed();
  }

  async restoreExpanded(id, savedNodes) {
    const saved = savedNodes[id];
    const parent = this.nodes.get(id);
    if (!parent?.expanded) return;
    const contents = await this.loadChildren(id), children = contents.folders;
    parent.files = contents.files; parent.folders = children; parent.childrenLoaded = true;
    for (const child of children) {
      const savedChild = savedNodes[child.id]; if (!savedChild) continue;
      this.nodes.set(child.id, { ...child, x: savedChild.x, y: savedChild.y, expanded: savedChild.expanded, childrenLoaded: false });
      await this.restoreExpanded(child.id, savedNodes);
    }
  }

  async addRoot(folder) {
    if (!this.nodes.has(folder.id)) {
      const center = this.screenToWorld(this.canvas.clientWidth / 2, this.canvas.clientHeight / 3);
      this.nodes.set(folder.id, { ...folder, expanded: true, childrenLoaded: false, x: center.x - 120, y: center.y });
    }
    const node = this.nodes.get(folder.id); await this.loadNode(node); this.selected = folder.id; this.render(); this.changed();
  }

  isVisible(node) {
    let current = node;
    while (current.parentId) {
      const parent = this.nodes.get(current.parentId);
      if (!parent || !parent.expanded) return false;
      current = parent;
    }
    return true;
  }

  render() {
    applyViewport(this.world, this.canvas.querySelector("#edges"), this.viewport);
    const visible = new Map([...this.nodes].filter(([, node]) => this.isVisible(node)));
    for (const [id, element] of this.elements) if (!visible.has(id)) { element.remove(); this.elements.delete(id); }
    for (const [id, node] of visible) {
      let element = this.elements.get(id);
      if (!element) { element = createNodeElement(node, this.handlers()); this.elements.set(id, element); this.world.append(element); }
      updateNodeElement(element, node, id === this.selected, this.selectedItem?.id, new Set([...this.nodes.values()].filter((child) => child.parentId === id).map((child) => child.id)), this.handlers());
      node.renderedHeight = element.offsetHeight;
    }
    renderEdges(this.edges, visible);
    document.querySelector("#empty-hint").hidden = this.nodes.size > 0;
  }

  async toggle(id) {
    const node = this.nodes.get(id);
    if (!node.expanded && !node.childrenLoaded) await this.loadNode(node);
    node.expanded = !node.expanded; this.render(); this.changed();
  }

  async loadNode(node) { const contents = await this.loadChildren(node.id); node.folders = contents.folders; node.files = contents.files; node.childrenLoaded = true; }

  handlers() { return { toggle: (id) => this.toggle(id), folder: (parentId, folder) => this.openChild(parentId, folder), drag: (event, id) => this.startDrag(event, id), selectFolder: (id) => this.selectFolder(id), selectFile: (file, element) => this.selectFile(file, element), open: (id) => this.actions.open?.(id), rename: () => this.actions.rename?.(), drop: (event, id) => this.actions.transfer?.(event.dataTransfer.getData("application/x-nodefilemanager-item"), id, event.altKey) }; }

  async openChild(parentId, folder) {
    if (this.nodes.has(folder.id)) { this.removeBranch(folder.id); this.layoutChildren(parentId); this.render(); this.changed(); return; }
    const parent = this.nodes.get(parentId); const child = { ...folder, parentId, expanded: true, childrenLoaded: false, x: parent.x, y: parent.y + 160 };
    this.nodes.set(folder.id, child); await this.loadNode(child); this.render(); this.layoutChildren(parentId); this.render(); this.changed();
  }

  layoutChildren(parentId) {
    const parent = this.nodes.get(parentId), children = [...this.nodes.values()].filter((node) => node.parentId === parentId); if (!parent || !children.length) return;
    const height = this.elements.get(parentId)?.offsetHeight || 80, y = parent.y + height + 22;
    if (children.length === 1) { children[0].x = parent.x; children[0].y = y; return; }
    const positions = childPositions({ ...parent, y: y - 130 }, children.length); children.forEach((child, index) => Object.assign(child, positions[index], { y }));
  }

  selectFolder(id) { this.clearSelection(); this.selected = id; this.elements.get(id)?.classList.add("selected"); }

  selectFile(file, element) {
    this.clearSelection(); this.selectedItem = file;
    element.classList.add("selected");
  }

  clearSelection() {
    this.world.querySelector(".file-item.selected")?.classList.remove("selected");
    if (this.selected) this.elements.get(this.selected)?.classList.remove("selected");
    this.selected = null; this.selectedItem = null;
  }

  async refresh(id = null) {
    const targets = id ? [this.nodes.get(id)] : [...this.nodes.values()].filter((node) => this.isVisible(node));
    for (const node of targets.filter(Boolean)) {
      if (!this.nodes.has(node.id)) continue;
      const contents = await this.loadChildren(node.id); node.childrenState = contents.files.length + contents.folders.length ? "present" : "empty"; node.hasChildren = node.childrenState === "present";
      const availableFolders = new Set(contents.folders.map((folder) => folder.id));
      [...this.nodes.values()].filter((child) => child.parentId === node.id && !availableFolders.has(child.id)).forEach((child) => this.removeBranch(child.id));
      if (node.expanded) {
        node.files = contents.files; node.folders = contents.folders; node.childrenLoaded = true;
      } else {
        node.files = []; node.childrenLoaded = false;
      }
    }
    this.render(); this.changed();
  }

  removeBranch(id) { for (const child of [...this.nodes.values()].filter((item) => item.parentId === id)) this.removeBranch(child.id); this.nodes.delete(id); }
  visibleFolders() { return [...this.nodes.values()].filter((node) => this.isVisible(node)); }

  applyRename(oldId, item) {
    if (item.kind === "file") return;
    const previous = this.nodes.get(oldId); if (!previous) return;
    this.removeBranch(oldId); this.elements.get(oldId)?.remove(); this.elements.delete(oldId);
    this.nodes.set(item.id, { ...previous, ...item, expanded: false, childrenLoaded: false, files: [] });
    this.selected = item.id; this.render(); this.changed();
  }

  startDrag(event, id) {
    if (event.button !== 0 || event.target.closest("button, .file-item")) return;
    this.finishDrag(false); event.stopPropagation();
    const node = this.nodes.get(id); if (!node) return;
    this.dragSession = { pointerId: event.pointerId, nodeId: id, element: event.currentTarget, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y, dragging: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  continueDrag(event) {
    const session = this.dragSession; if (!session || session.pointerId !== event.pointerId) return;
    const dx = event.clientX - session.startX, dy = event.clientY - session.startY;
    if (!session.dragging && Math.hypot(dx, dy) < 5) return;
    if (!session.dragging) { session.dragging = true; this.selectFolder(session.nodeId); }
    const node = this.nodes.get(session.nodeId); if (!node) { this.finishDrag(false); return; }
    node.x = session.originX + dx / this.viewport.zoom; node.y = session.originY + dy / this.viewport.zoom; this.render();
  }

  endDrag(event) {
    const session = this.dragSession; if (!session || session.pointerId !== event.pointerId) return;
    const wasDragging = session.dragging, nodeId = session.nodeId; this.finishDrag(true);
    if (!wasDragging) this.selectFolder(nodeId);
  }

  cancelDrag(event) { if (this.dragSession?.pointerId === event.pointerId) this.finishDrag(false); }

  finishDrag(savePosition) {
    const session = this.dragSession; if (!session) return;
    this.dragSession = null;
    if (session.element.hasPointerCapture?.(session.pointerId)) session.element.releasePointerCapture(session.pointerId);
    if (savePosition && session.dragging) this.changed();
    else if (session.dragging) {
      const node = this.nodes.get(session.nodeId);
      if (node) { node.x = session.originX; node.y = session.originY; this.render(); }
    }
  }

  escape(event) {
    const active = this.dragSession || this.selected || this.selectedItem || this.actions.dialogOpen?.();
    this.finishDrag(false); this.clearSelection(); this.actions.cancelDialog?.();
    if (active) event.preventDefault();
  }

  startPan(event) {
    const isNodeInteraction = event.target.closest?.(".folder-node");
    if (isNodeInteraction || event.button !== 0) return;
    this.canvas.setPointerCapture(event.pointerId); this.canvas.classList.add("panning");
    const startX = event.clientX, startY = event.clientY, x = this.viewport.x, y = this.viewport.y;
    const move = (moveEvent) => { this.viewport.x = x + moveEvent.clientX - startX; this.viewport.y = y + moveEvent.clientY - startY; this.render(); };
    const end = () => { this.canvas.removeEventListener("pointermove", move); this.canvas.classList.remove("panning"); this.changed(); };
    this.canvas.addEventListener("pointermove", move); this.canvas.addEventListener("pointerup", end, { once: true });
  }

  zoom(event) {
    event.preventDefault(); const rect = this.canvas.getBoundingClientRect(); const sx = event.clientX - rect.left, sy = event.clientY - rect.top;
    const old = this.viewport.zoom, next = Math.min(2.5, Math.max(.25, old * Math.exp(-event.deltaY * .001)));
    this.viewport.x = sx - (sx - this.viewport.x) * next / old; this.viewport.y = sy - (sy - this.viewport.y) * next / old; this.viewport.zoom = next;
    this.render(); this.changed();
  }

  screenToWorld(x, y) { return { x: (x - this.viewport.x) / this.viewport.zoom, y: (y - this.viewport.y) / this.viewport.zoom }; }
  changed() { this.onChange(this.serialize()); }
  serialize() {
    const nodes = Object.fromEntries([...this.nodes].map(([id, node]) => {
      const { childrenLoaded, folders, files, renderedHeight, ...persistentNode } = node;
      return [id, persistentNode];
    }));
    const roots = [...this.nodes.values()].filter((node) => !node.parentId).map(({ id, path }) => ({ id, path }));
    return { version: 1, roots, nodes, viewport: this.viewport };
  }
}
