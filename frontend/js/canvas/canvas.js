import { createNodeElement, updateNodeElement } from "./node.js";
import { applyViewport } from "./viewport.js";

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
        childrenLoaded: false,
      });
    }
    this.render();
    for (const root of availableRoots) await this.restoreMaterialized(root.id, savedNodes);
    this.render(); for (const root of availableRoots) this.layoutTree(root.id); this.render();
    this.changed();
  }

  async restoreMaterialized(id, savedNodes) {
    const saved = savedNodes[id];
    const parent = this.nodes.get(id);
    if (!parent) return;
    const contents = await this.loadChildren(id), children = contents.folders;
    parent.files = contents.files; parent.folders = children; parent.childrenLoaded = true;
    for (const child of children) {
      const savedChild = savedNodes[child.id]; if (!savedChild) continue;
      this.nodes.set(child.id, { ...child, x: savedChild.x, y: savedChild.y, childrenLoaded: false });
      await this.restoreMaterialized(child.id, savedNodes);
    }
  }

  async addRoot(folder) {
    if (!this.nodes.has(folder.id)) {
      const center = this.screenToWorld(this.canvas.clientWidth / 2, this.canvas.clientHeight / 3);
      this.nodes.set(folder.id, { ...folder, childrenLoaded: false, x: center.x - 120, y: center.y });
    }
    const node = this.nodes.get(folder.id); await this.loadNode(node); this.selected = folder.id; this.render(); this.changed();
  }

  isVisible(node) {
    let current = node;
    while (current.parentId) {
      const parent = this.nodes.get(current.parentId);
      if (!parent) return false;
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
      element.classList.toggle("attached", Boolean(node.parentId));
      element.classList.toggle("has-open-children", [...this.nodes.values()].some((child) => child.parentId === id));
      updateNodeElement(element, node, id === this.selected, this.selectedItem?.id, new Set([...this.nodes.values()].filter((child) => child.parentId === id).map((child) => child.id)), this.handlers());
      node.renderedHeight = element.offsetHeight;
    }
    this.edges.replaceChildren();
    document.querySelector("#empty-hint").hidden = this.nodes.size > 0;
  }

  async loadNode(node) { const contents = await this.loadChildren(node.id); node.folders = contents.folders; node.files = contents.files; node.childrenLoaded = true; }

  handlers() { return { folder: (parentId, folder) => this.openChild(parentId, folder), close: (id) => this.closeNode(id), newFolder: (id) => this.actions.newFolder?.(id), preview: (ownerId, file) => this.preview(ownerId, file), closePreview: (id) => this.closePreview(id), previewPage: (id, delta) => this.previewPage(id, delta), drag: (event, id) => this.startDrag(event, id), selectFolder: (id) => this.selectFolder(id), selectFile: (file, element) => this.selectFile(file, element), open: (id) => this.actions.open?.(id), rename: () => this.actions.rename?.(), drop: (event, id) => this.actions.transfer?.(event.dataTransfer.getData("application/x-nodefilemanager-item"), id, event.altKey) }; }

  async openChild(parentId, folder) {
    if (this.nodes.has(folder.id)) { this.removeBranch(folder.id); this.render(); this.layoutTree(parentId); this.render(); this.changed(); return; }
    const parent = this.nodes.get(parentId); const child = { ...folder, parentId, childrenLoaded: false, x: parent.x, y: parent.y + 160 };
    this.nodes.set(folder.id, child); await this.loadNode(child); this.render(); this.layoutTree(parentId); this.render(); this.changed();
  }

  layoutTree(parentId) {
    const parent = this.nodes.get(parentId), children = [...this.nodes.values()].filter((node) => node.parentId === parentId).sort((left, right) => left.x - right.x); if (!parent || !children.length) return;
    const height = this.elements.get(parentId)?.offsetHeight || 80, y = parent.y + height;
    if (children.length === 1) { children[0].x = parent.x; children[0].y = y; this.layoutTree(children[0].id); return; }
    const width = 240, gap = 8, start = parent.x + width / 2 - (children.length * width + (children.length - 1) * gap) / 2;
    children.forEach((child, index) => { child.x = start + index * (width + gap); child.y = y; });
    children.forEach((child) => this.layoutTree(child.id));
  }

  closeNode(id) { const node = this.nodes.get(id); if (!node) return; const parentId = node.parentId; this.removeBranch(id); this.render(); if (parentId) this.layoutTree(parentId); this.render(); this.changed(); }

  preview(ownerId, file) {
    const owner = this.nodes.get(ownerId);
    if (![".pdf", ".jpg", ".jpeg", ".png"].includes((file.extension || "").toLowerCase())) { if (owner.preview) this.closePreview(ownerId); return; }
    owner.preview = { ...file, page: 1 }; this.render(); this.layoutTree(ownerId); this.render(); this.changed();
  }
  closePreview(id) { const node = this.nodes.get(id); if (!node) return; delete node.preview; this.render(); this.layoutTree(id); this.render(); this.changed(); }
  previewPage(id, delta) { const preview = this.nodes.get(id)?.preview; if (!preview) return; preview.page = Math.max(1, preview.page + delta); this.render(); }

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
      if (node.preview && !contents.files.some((file) => file.id === node.preview.id)) delete node.preview;
      const availableFolders = new Set(contents.folders.map((folder) => folder.id));
      [...this.nodes.values()].filter((child) => child.parentId === node.id && !availableFolders.has(child.id)).forEach((child) => this.removeBranch(child.id));
      node.files = contents.files; node.folders = contents.folders; node.childrenLoaded = true;
    }
    this.render(); for (const root of [...this.nodes.values()].filter((node) => !node.parentId)) this.layoutTree(root.id); this.render(); this.changed();
  }

  removeBranch(id) { for (const child of [...this.nodes.values()].filter((item) => item.parentId === id)) this.removeBranch(child.id); this.nodes.delete(id); }
  visibleFolders() { return [...this.nodes.values()].filter((node) => this.isVisible(node)); }

  async applyRename(oldId, item) {
    if (item.kind === "file") return;
    const previous = this.nodes.get(oldId); if (!previous) return;
    const parentId = previous.parentId;
    this.removeBranch(oldId); this.elements.get(oldId)?.remove(); this.elements.delete(oldId);
    const renamed = { ...previous, ...item, childrenLoaded: false, folders: [], files: [] }; delete renamed.preview;
    this.nodes.set(item.id, renamed); await this.loadNode(renamed);
    this.selected = item.id; this.render(); if (parentId) this.layoutTree(parentId); else this.layoutTree(item.id); this.render(); this.changed();
  }

  startDrag(event, id) {
    if (event.button !== 0 || event.target.closest("button, .file-item, .folder-item, iframe")) return;
    this.finishDrag(false); event.stopPropagation();
    const node = this.nodes.get(id); if (!node) return;
    let root = node; while (root.parentId && this.nodes.has(root.parentId)) root = this.nodes.get(root.parentId);
    const members = [root, ...this.descendants(root.id)], origins = new Map(members.map((member) => [member.id, { x: member.x, y: member.y }]));
    this.dragSession = { pointerId: event.pointerId, nodeId: id, element: event.currentTarget, startX: event.clientX, startY: event.clientY, origins, dragging: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  continueDrag(event) {
    const session = this.dragSession; if (!session || session.pointerId !== event.pointerId) return;
    const dx = event.clientX - session.startX, dy = event.clientY - session.startY;
    if (!session.dragging && Math.hypot(dx, dy) < 5) return;
    if (!session.dragging) { session.dragging = true; this.selectFolder(session.nodeId); }
    for (const [id, origin] of session.origins) { const member = this.nodes.get(id); if (member) { member.x = origin.x + dx / this.viewport.zoom; member.y = origin.y + dy / this.viewport.zoom; } } this.render();
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
      for (const [id, origin] of session.origins) { const node = this.nodes.get(id); if (node) { node.x = origin.x; node.y = origin.y; } } this.render();
    }
  }

  descendants(id) { const direct = [...this.nodes.values()].filter((node) => node.parentId === id); return direct.flatMap((node) => [node, ...this.descendants(node.id)]); }

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
      const { childrenLoaded, folders, files, preview, renderedHeight, ...persistentNode } = node;
      return [id, persistentNode];
    }));
    const roots = [...this.nodes.values()].filter((node) => !node.parentId).map(({ id, path }) => ({ id, path }));
    return { version: 1, roots, nodes, viewport: this.viewport };
  }
}
