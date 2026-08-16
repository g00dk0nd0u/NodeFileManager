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
        expanded: false,
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
    if (!saved?.expanded || !parent?.hasChildren) return;
    const contents = await this.loadChildren(id), children = contents.folders;
    parent.files = contents.files; parent.childrenState = contents.folders.length + contents.files.length ? "present" : "empty"; parent.hasChildren = parent.childrenState === "present";
    const positions = childPositions(parent, children.length);
    for (const [index, child] of children.entries()) {
      const savedChild = savedNodes[child.id];
      this.nodes.set(child.id, {
        ...child,
        x: savedChild?.x ?? positions[index].x,
        y: savedChild?.y ?? positions[index].y,
        expanded: false,
        childrenLoaded: false,
      });
    }
    parent.childrenLoaded = true;
    parent.expanded = true;
    for (const child of children) await this.restoreExpanded(child.id, savedNodes);
  }

  addRoot(folder) {
    if (!this.nodes.has(folder.id)) {
      const center = this.screenToWorld(this.canvas.clientWidth / 2, this.canvas.clientHeight / 3);
      this.nodes.set(folder.id, { ...folder, expanded: false, x: center.x - 90, y: center.y });
    }
    this.selected = folder.id; this.render(); this.changed();
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
      updateNodeElement(element, node, id === this.selected, this.selectedItem?.id, this.handlers());
    }
    renderEdges(this.edges, visible);
    document.querySelector("#empty-hint").hidden = this.nodes.size > 0;
  }

  async toggle(id) {
    const node = this.nodes.get(id);
    if (!node.expanded && !node.childrenLoaded) {
      const contents = await this.loadChildren(id), children = contents.folders;
      node.files = contents.files; node.childrenState = children.length + contents.files.length ? "present" : "empty"; node.hasChildren = node.childrenState === "present";
      this.reconcileChildren(node, children);
      node.childrenLoaded = true;
    }
    node.expanded = !node.expanded; this.render(); this.changed();
  }

  handlers() { return { toggle: (id) => this.toggle(id), drag: (event, id) => this.startDrag(event, id), selectFolder: (id) => this.selectFolder(id), selectFile: (file, element) => this.selectFile(file, element), open: (id) => this.actions.open?.(id), rename: () => this.actions.rename?.(), drop: (event, id) => this.actions.transfer?.(event.dataTransfer.getData("application/x-nodefilemanager-item"), id, event.altKey) }; }

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
      if (node.expanded) {
        node.files = contents.files; this.reconcileChildren(node, contents.folders); node.childrenLoaded = true;
      } else {
        node.files = []; node.childrenLoaded = false;
      }
    }
    this.render(); this.changed();
  }

  reconcileChildren(node, children) {
    const current = [...this.nodes.values()].filter((child) => child.parentId === node.id);
    const incoming = new Set(children.map((child) => child.id));
    current.filter((child) => !incoming.has(child.id)).forEach((child) => this.removeBranch(child.id));
    const positions = childPositions(node, children.length);
    children.forEach((child, index) => {
      const existing = this.nodes.get(child.id);
      if (existing) Object.assign(existing, child);
      else this.nodes.set(child.id, { ...child, ...positions[index], expanded: false, childrenLoaded: false });
    });
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
      const { childrenLoaded, files, ...persistentNode } = node;
      return [id, persistentNode];
    }));
    const roots = [...this.nodes.values()].filter((node) => !node.parentId).map(({ id, path }) => ({ id, path }));
    return { version: 1, roots, nodes, viewport: this.viewport };
  }
}
