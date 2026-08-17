import { createNodeElement, updateNodeElement, updatePreviewElement } from "./node.js";
import { applyViewport } from "./viewport.js";

const uid = (prefix) => `${prefix}-${crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`}`;

export class FolderCanvas {
  constructor(element, onChange, loadChildren) {
    this.canvas = element; this.world = element.querySelector("#world"); this.edges = element.querySelector("#edges g");
    this.nodes = new Map(); this.elements = new Map(); this.workingSets = new Map(); this.setElements = new Map();
    this.viewport = { x: 0, y: 0, zoom: 1 }; this.selected = null; this.selectedItem = null;
    this.onChange = onChange; this.loadChildren = loadChildren; this.actions = {}; this.dragSession = null;
    this.canvas.addEventListener("pointerdown", (event) => this.startPan(event));
    this.canvas.addEventListener("wheel", (event) => this.zoom(event), { passive: false });
    this.canvas.addEventListener("contextmenu", (event) => { if (!event.target.closest(".folder-node,.working-set")) { event.preventDefault(); this.actions.canvasMenu?.(event.clientX, event.clientY); } });
    window.addEventListener("pointermove", (event) => this.continueDrag(event)); window.addEventListener("pointerup", (event) => this.endDrag(event));
    window.addEventListener("pointercancel", (event) => this.cancelDrag(event)); window.addEventListener("blur", () => this.finishDrag(false));
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") this.escape(event); });
  }

  async restore(state, availableRoots) {
    this.viewport = { x: 0, y: 0, zoom: 1, ...(state.viewport || {}) }; this.nodes.clear(); this.workingSets.clear();
    for (const [id, set] of Object.entries(state.workingSets || {})) this.workingSets.set(id, { workingSetId: id, name: "Working Set", ...set });
    const saved = state.nodes || {};
    for (const [index, root] of availableRoots.entries()) {
      const record = saved[root.panelInstanceId] || Object.values(saved).find((node) => node.folderId === root.id && (!root.workingSetId || node.workingSetId === root.workingSetId)) || saved[root.id];
      const setId = record?.workingSetId || this.newSet(); if (!this.workingSets.has(setId)) this.workingSets.set(setId, { workingSetId: setId, name: "Working Set" });
      const panelId = record?.panelInstanceId || uid("panel");
      this.nodes.set(panelId, { ...root, ...record, id: root.id, folderId: root.id, panelInstanceId: panelId, workingSetId: setId,
        visualParentPanelId: record?.visualParentPanelId ?? null, fsParentFolderId: record?.fsParentFolderId ?? null,
        x: record?.x ?? index * 320 + 80, y: record?.y ?? 100, childrenLoaded: false });
    }
    for (const panel of [...this.nodes.values()]) await this.restoreMaterialized(panel, saved);
    this.render(); this.changed();
  }

  async restoreMaterialized(panel, saved) {
    await this.loadNode(panel);
    for (const record of Object.values(saved)) {
      if (record.visualParentPanelId !== panel.panelInstanceId || record.workingSetId !== panel.workingSetId) continue;
      const folder = panel.folders.find((item) => item.id === record.folderId || item.path === record.path); if (!folder) continue;
      const child = { ...folder, ...record, id: folder.id, folderId: folder.id, childrenLoaded: false };
      this.nodes.set(child.panelInstanceId, child); await this.restoreMaterialized(child, saved);
    }
  }

  newSet() { const id = uid("working-set"); this.workingSets.set(id, { workingSetId: id, name: "Working Set" }); return id; }
  async addRoot(folder) {
    const center = this.screenToWorld(this.canvas.clientWidth / 2, this.canvas.clientHeight / 3), setId = this.newSet();
    const panel = { ...folder, id: folder.id, folderId: folder.id, panelInstanceId: uid("panel"), workingSetId: setId,
      visualParentPanelId: null, fsParentFolderId: folder.parentId || null, x: center.x - 130, y: center.y, childrenLoaded: false };
    this.nodes.set(panel.panelInstanceId, panel); await this.loadNode(panel); this.selected = panel.panelInstanceId; this.render(); this.changed();
  }
  async loadNode(node) { const contents = await this.loadChildren(node.folderId); node.folders = contents.folders; node.files = contents.files; node.childrenLoaded = true;
    if (!node.visualParentPanelId && this.actions.getParent) { const response = await this.actions.getParent(node.folderId); node.compactParent = response.parent; node.fsParentFolderId = response.parent?.id || null; } }
  panelForFolder(folderId, setId) { return [...this.nodes.values()].find((node) => node.folderId === folderId && node.workingSetId === setId); }
  descendants(panelId) { const direct = [...this.nodes.values()].filter((node) => node.visualParentPanelId === panelId); return direct.flatMap((node) => [node, ...this.descendants(node.panelInstanceId)]); }

  handlers() { return { folder: (panelId, folder) => this.openChild(panelId, folder), parent: (id) => this.openParent(id), close: (id) => this.closeNode(id), search: (id) => this.actions.localSearch?.(id),
    isolate: (id) => this.isolate(id), reattach: (id) => this.reattach(id), newFolder: (id) => this.actions.newFolder?.(this.nodes.get(id)?.folderId),
    preview: (id, file) => this.preview(id, file), closePreview: (id) => this.closePreview(id), previewPage: (id, delta) => this.previewPage(id, delta), previewResized: (id) => this.previewResized(id),
    drag: (event, id) => this.startDrag(event, id), selectFolder: (id) => this.selectFolder(id), selectFile: (file, el) => this.selectFile(file, el), open: (id) => this.actions.open?.(id), rename: () => this.actions.rename?.(),
    folderDrag: (event, id) => { const node=this.nodes.get(id); event.dataTransfer.setData("application/x-nodefilemanager-item",node.folderId); event.dataTransfer.setData("application/x-nodefilemanager-kind","folder"); event.dataTransfer.effectAllowed="move"; }, drop: (event, id, region) => this.dropFilesystem(event, id, region) }; }

  async openChild(parentPanelId, folder) {
    const parent = this.nodes.get(parentPanelId), existing = this.panelForFolder(folder.id, parent.workingSetId);
    if (existing) { this.revealPanel(existing.panelInstanceId, folder.id); return; }
    const siblings = [...this.nodes.values()].filter((node) => node.visualParentPanelId === parentPanelId);
    const child = { ...folder, id: folder.id, folderId: folder.id, panelInstanceId: uid("panel"), workingSetId: parent.workingSetId,
      visualParentPanelId: parentPanelId, fsParentFolderId: parent.folderId, childrenLoaded: false,
      x: siblings.length ? parent.x + siblings.length * 280 : parent.x + 300, y: siblings.length ? parent.y + 260 : parent.y };
    this.nodes.set(child.panelInstanceId, child); await this.loadNode(child); this.render(); this.changed(); this.actions.visit?.(folder.id);
  }
  async openParent(childId) { const child=this.nodes.get(childId), folder=child?.compactParent; if(!child||!folder)return; const existing=this.panelForFolder(folder.id,child.workingSetId); if(existing){child.visualParentPanelId=existing.panelInstanceId;this.render();this.changed();return;}
    const parent={...folder,id:folder.id,folderId:folder.id,panelInstanceId:uid("panel"),workingSetId:child.workingSetId,visualParentPanelId:null,fsParentFolderId:null,x:child.x-300,y:child.y,childrenLoaded:false}; child.visualParentPanelId=parent.panelInstanceId; delete child.compactParent; this.nodes.set(parent.panelInstanceId,parent); await this.loadNode(parent); this.render();this.changed(); }
  revealPanel(panelId, rowId = null) { const node = this.nodes.get(panelId); if (!node) return false; this.clearSelection(); this.selected = panelId; this.render();
    this.viewport.x = this.canvas.clientWidth / 2 - (node.x + 130) * this.viewport.zoom; this.viewport.y = this.canvas.clientHeight / 2 - (node.y + 80) * this.viewport.zoom; this.updateViewport();
    const row = rowId && this.elements.get(panelId)?.querySelector(`[data-id="${CSS.escape(rowId)}"]`); if (row) { row.classList.add("match-pulse"); setTimeout(() => row.classList.remove("match-pulse"), 1200); } return true; }
  revealNode(folderId) { const panel = [...this.nodes.values()].find((node) => node.folderId === folderId); return panel ? this.revealPanel(panel.panelInstanceId) : false; }

  render() {
    this.updateViewport(); this.renderSets();
    for (const [id, element] of this.elements) if (!this.nodes.has(id)) { element.remove(); this.elements.delete(id); }
    for (const [id, node] of this.nodes) { let element = this.elements.get(id); if (!element) { element = createNodeElement(node, this.handlers()); this.elements.set(id, element); this.world.append(element); }
      updateNodeElement(element, node, id === this.selected, this.selectedItem?.id, new Set([...this.nodes.values()].filter((child) => child.visualParentPanelId === id).map((child) => child.folderId)), this.handlers()); node.renderedHeight = element.offsetHeight; }
    this.renderEdges(); document.querySelector("#empty-hint").hidden = this.nodes.size > 0;
  }
  renderSets() {
    for (const [id, element] of this.setElements) if (!this.workingSets.has(id) || ![...this.nodes.values()].some((n) => n.workingSetId === id)) { element.remove(); this.setElements.delete(id); }
    for (const [id, set] of this.workingSets) { const members = [...this.nodes.values()].filter((n) => n.workingSetId === id); if (!members.length) continue;
      let el = this.setElements.get(id); if (!el) { el = document.createElement("section"); el.className = "working-set"; el.innerHTML = `<span></span>`; el.querySelector("span").textContent = set.name || "Working Set"; this.world.prepend(el); this.setElements.set(id, el); }
      const minX = Math.min(...members.map(n => n.x)) - 42, minY = Math.min(...members.map(n => n.y)) - 58, maxX = Math.max(...members.map(n => n.x + 260)) + 42, maxY = Math.max(...members.map(n => n.y + (n.renderedHeight || 220))) + 42;
      Object.assign(el.style, { transform: `translate(${minX}px,${minY}px)`, width: `${maxX-minX}px`, height: `${maxY-minY}px` }); }
  }
  renderEdges() { this.edges.replaceChildren(); for (const child of this.nodes.values()) { const parent = this.nodes.get(child.visualParentPanelId); if (!parent) continue; const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); const x1=parent.x+260, y1=parent.y+32, x2=child.x, y2=child.y+32; path.setAttribute("d", `M${x1} ${y1} L${x2} ${y2}`); this.edges.append(path); } }

  isolate(panelId) { const root = this.nodes.get(panelId); if (!root || !root.visualParentPanelId) return; const setId = this.newSet(); root.visualParentPanelId = null; for (const node of [root, ...this.descendants(panelId)]) node.workingSetId = setId; root.x += 80; root.y += 80; this.cleanupSets(); this.render(); this.changed(); }
  reattach(panelId, destinationSetId = null) { const root = this.nodes.get(panelId); if (!root || root.visualParentPanelId || !root.fsParentFolderId) return false;
    const parent = [...this.nodes.values()].find((node) => node.folderId === root.fsParentFolderId && node.workingSetId !== root.workingSetId && (!destinationSetId || node.workingSetId === destinationSetId)); if (!parent) return false;
    if (this.panelForFolder(root.folderId, parent.workingSetId)) return false; const old = root.workingSetId; root.visualParentPanelId = parent.panelInstanceId;
    for (const node of [root, ...this.descendants(panelId)]) node.workingSetId = parent.workingSetId; root.x=parent.x+300; root.y=parent.y; this.workingSets.delete(old); this.render(); this.changed(); return true; }
  cleanupSets() { for (const id of [...this.workingSets.keys()]) if (![...this.nodes.values()].some(n => n.workingSetId === id)) this.workingSets.delete(id); }
  closeNode(panelId) { for (const node of [this.nodes.get(panelId), ...this.descendants(panelId)].filter(Boolean)) this.nodes.delete(node.panelInstanceId); this.cleanupSets(); this.clearSelection(); this.render(); this.changed(); }

  dropFilesystem(event, destinationFolderId, region) { const kind=event.dataTransfer.getData("application/x-nodefilemanager-kind"), id=event.dataTransfer.getData("application/x-nodefilemanager-item"); if (!id || kind !== region) return; this.actions.transfer?.(id, destinationFolderId, event.altKey, kind); }
  preview(panelId, file) { const node=this.nodes.get(panelId); if (![".pdf",".jpg",".jpeg",".png"].includes((file.extension||"").toLowerCase())) { if(node?.preview)this.closePreview(panelId); return; } node.preview={...file,page:1}; this.updatePreview(panelId); this.changed(); }
  closePreview(id){const n=this.nodes.get(id);if(!n)return;delete n.preview;this.updatePreview(id);this.changed();} previewPage(id,d){const p=this.nodes.get(id)?.preview;if(!p)return;p.page=Math.max(1,p.page+d);this.updatePreview(id);}
  updatePreview(id){const n=this.nodes.get(id),e=this.elements.get(id);if(n&&e)updatePreviewElement(e,n,this.handlers());} previewResized(id){const n=this.nodes.get(id),e=this.elements.get(id);if(n&&e)n.renderedHeight=e.offsetHeight;this.renderSets();}
  selectFolder(id){this.clearSelection();this.selected=id;this.elements.get(id)?.classList.add("selected");} selectFile(file,el){this.clearSelection();this.selectedItem=file;el.classList.add("selected");}
  clearSelection(){this.world.querySelector(".file-item.selected")?.classList.remove("selected");if(this.selected)this.elements.get(this.selected)?.classList.remove("selected");this.selected=null;this.selectedItem=null;}
  updateFavoriteStates() {}
  visibleFolders(){return [...this.nodes.values()];}
  async refresh(folderId=null){const targets=folderId?[...this.nodes.values()].filter(n=>n.folderId===folderId):[...this.nodes.values()];for(const node of targets)await this.loadNode(node);this.render();this.changed();}
  async applyRename(oldId,item){for(const node of [...this.nodes.values()].filter(n=>n.folderId===oldId)){node.id=item.id;node.folderId=item.id;node.name=item.name;node.path=item.path;await this.loadNode(node);}this.render();this.changed();}

  startDrag(event,id){if(event.button!==0||event.target.closest("button,.file-item,.folder-item,input,iframe"))return;this.finishDrag(false);const root=this.nodes.get(id);if(!root)return;const members=[root,...this.descendants(id)],origins=new Map(members.map(n=>[n.panelInstanceId,{x:n.x,y:n.y}]));this.dragSession={pointerId:event.pointerId,nodeId:id,element:event.currentTarget,startX:event.clientX,startY:event.clientY,origins,dragging:false};event.currentTarget.setPointerCapture(event.pointerId);}
  continueDrag(event){const s=this.dragSession;if(!s||s.pointerId!==event.pointerId)return;const dx=event.clientX-s.startX,dy=event.clientY-s.startY;if(!s.dragging&&Math.hypot(dx,dy)<5)return;s.dragging=true;for(const[id,o]of s.origins){const n=this.nodes.get(id);if(n){n.x=o.x+dx/this.viewport.zoom;n.y=o.y+dy/this.viewport.zoom;}}this.updatePositions();this.renderSets();this.renderEdges();}
  endDrag(event){const s=this.dragSession;if(!s||s.pointerId!==event.pointerId)return;const moved=s.dragging,id=s.nodeId;this.finishDrag(true);if(!moved)this.selectFolder(id);else{const root=this.nodes.get(id),box=this.setElements.get(root.workingSetId)?.getBoundingClientRect(),point={x:event.clientX,y:event.clientY};if(root.visualParentPanelId&&box&&(point.x<box.left||point.x>box.right||point.y<box.top||point.y>box.bottom))this.isolate(id);else this.tryReattachAt(id,event.clientX,event.clientY);}}
  tryReattachAt(id,x,y){const root=this.nodes.get(id);if(root?.visualParentPanelId)return;const destination=[...this.setElements].find(([setId,el])=>setId!==root.workingSetId&&(()=>{const r=el.getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom;})());if(destination)this.reattach(id,destination[0]);}
  cancelDrag(event){if(this.dragSession?.pointerId===event.pointerId)this.finishDrag(false);} finishDrag(save){const s=this.dragSession;if(!s)return;this.dragSession=null;if(s.element.hasPointerCapture?.(s.pointerId))s.element.releasePointerCapture(s.pointerId);if(save&&s.dragging)this.changed();else if(s.dragging){for(const[id,o]of s.origins){const n=this.nodes.get(id);if(n)Object.assign(n,o);}this.updatePositions();}}
  updatePositions(){for(const[id,el]of this.elements){const n=this.nodes.get(id);if(n)el.style.transform=`translate(${n.x}px,${n.y}px)`;}} updateViewport(){applyViewport(this.world,this.canvas.querySelector("#edges"),this.viewport);}
  escape(event){const active=this.dragSession||this.selected||this.selectedItem||this.actions.dialogOpen?.();this.finishDrag(false);this.clearSelection();this.actions.cancelDialog?.();if(active)event.preventDefault();}
  startPan(event){if(event.target.closest?.(".folder-node,.working-set")||event.button!==0)return;this.canvas.setPointerCapture(event.pointerId);this.canvas.classList.add("panning");const sx=event.clientX,sy=event.clientY,x=this.viewport.x,y=this.viewport.y;const move=e=>{this.viewport.x=x+e.clientX-sx;this.viewport.y=y+e.clientY-sy;this.updateViewport();};const end=()=>{this.canvas.removeEventListener("pointermove",move);this.canvas.classList.remove("panning");this.changed();};this.canvas.addEventListener("pointermove",move);this.canvas.addEventListener("pointerup",end,{once:true});}
  zoom(event){event.preventDefault();const r=this.canvas.getBoundingClientRect(),sx=event.clientX-r.left,sy=event.clientY-r.top,old=this.viewport.zoom,next=Math.min(2.5,Math.max(.25,old*Math.exp(-event.deltaY*.001)));this.viewport.x=sx-(sx-this.viewport.x)*next/old;this.viewport.y=sy-(sy-this.viewport.y)*next/old;this.viewport.zoom=next;this.updateViewport();this.changed();}
  screenToWorld(x,y){return{x:(x-this.viewport.x)/this.viewport.zoom,y:(y-this.viewport.y)/this.viewport.zoom};} changed(){this.onChange(this.serialize());}
  serialize(){const nodes=Object.fromEntries([...this.nodes].map(([id,n])=>{const{childrenLoaded,folders,files,preview,renderedHeight,compactParent,...saved}=n;return[id,saved];}));const roots=[...this.nodes.values()].filter(n=>!n.visualParentPanelId).map(({folderId,panelInstanceId,workingSetId,path})=>({id:folderId,panelInstanceId,workingSetId,path}));return{version:2,roots,nodes,workingSets:Object.fromEntries(this.workingSets),viewport:this.viewport};}
}
