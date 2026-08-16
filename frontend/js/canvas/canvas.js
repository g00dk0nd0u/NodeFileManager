import { createNodeElement, updateNodeElement } from "./node.js";
import { renderEdges } from "./edge.js";
import { applyViewport } from "./viewport.js";
import { childPositions } from "./layout.js";

export class FolderCanvas {
  constructor(element, onChange, loadChildren) {
    this.canvas = element; this.world = element.querySelector("#world"); this.edges = element.querySelector("#edges g");
    this.nodes = new Map(); this.elements = new Map(); this.viewport = { x: 0, y: 0, zoom: 1 };
    this.selected = null; this.selectedItem = null; this.onChange = onChange; this.loadChildren = loadChildren;
    this.actions = {};
    this.canvas.addEventListener("pointerdown", (event) => this.startPan(event));
    this.canvas.addEventListener("wheel", (event) => this.zoom(event), { passive: false });
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
    parent.files = contents.files;
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
      node.files = contents.files;
      const positions = childPositions(node, children.length);
      children.forEach((child, index) => { if (!this.nodes.has(child.id)) this.nodes.set(child.id, { ...child, ...positions[index], expanded: false, childrenLoaded: false }); });
      node.childrenLoaded = true;
    }
    node.expanded = !node.expanded; this.render(); this.changed();
  }

  handlers() { return { toggle: (id) => this.toggle(id), drag: (event, id) => this.startDrag(event, id), selectFolder: (id) => { this.selected = id; this.selectedItem = null; this.render(); }, selectFile: (file) => { this.selectedItem = file; this.render(); }, open: (id) => this.actions.open?.(id), rename: () => this.actions.rename?.(), drop: (event, id) => this.actions.transfer?.(event.dataTransfer.getData("application/x-nodefilemanager-item"), id, event.altKey) }; }

  async refresh(id = null) {
    const targets = id ? [this.nodes.get(id)] : [...this.nodes.values()].filter((node) => node.expanded && this.isVisible(node));
    for (const node of targets.filter(Boolean)) {
      if (!this.nodes.has(node.id)) continue;
      const contents = await this.loadChildren(node.id); node.files = contents.files; node.hasChildren = contents.files.length + contents.folders.length > 0;
      const currentChildren = [...this.nodes.values()].filter((child) => child.parentId === node.id);
      const incoming = new Set(contents.folders.map((child) => child.id));
      currentChildren.filter((child) => !incoming.has(child.id)).forEach((child) => this.removeBranch(child.id));
      const positions = childPositions(node, contents.folders.length);
      contents.folders.forEach((child, index) => { if (!this.nodes.has(child.id)) this.nodes.set(child.id, { ...child, ...positions[index], expanded: false, childrenLoaded: false }); });
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
    if (event.button !== 0) return;
    event.stopPropagation(); event.currentTarget.setPointerCapture(event.pointerId); this.selected = id;
    const node = this.nodes.get(id), startX = event.clientX, startY = event.clientY, originX = node.x, originY = node.y;
    const move = (moveEvent) => { node.x = originX + (moveEvent.clientX - startX) / this.viewport.zoom; node.y = originY + (moveEvent.clientY - startY) / this.viewport.zoom; this.render(); };
    const end = () => { event.currentTarget.removeEventListener("pointermove", move); this.changed(); };
    event.currentTarget.addEventListener("pointermove", move); event.currentTarget.addEventListener("pointerup", end, { once: true }); this.render();
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
