import { createNodeElement, updateNodeElement, updatePreviewElement } from "./node.js";
import { applyViewport } from "./viewport.js";
import { panelWidth } from "./layout.js";

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
        x: record?.x ?? index * 460 + 80, y: record?.y ?? 100, childrenLoaded: false });
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
      visualParentPanelId: null, fsParentFolderId: folder.parentId || null, x: center.x - panelWidth(folder) / 2, y: center.y, childrenLoaded: false };
    this.nodes.set(panel.panelInstanceId, panel); await this.loadNode(panel); this.selected = panel.panelInstanceId; this.render(); this.changed();
  }
  async loadNode(node) { const contents = await this.loadChildren(node.folderId); node.folders = contents.folders; node.files = contents.files; node.childrenLoaded = true;
    if (!node.visualParentPanelId && this.actions.getParent) { const response = await this.actions.getParent(node.folderId); node.compactParent = response.parent; node.fsParentFolderId = response.parent?.id || null; } }
  panelForFolder(folderId, setId) { return [...this.nodes.values()].find((node) => node.folderId === folderId && node.workingSetId === setId); }
  descendants(panelId) { const direct = [...this.nodes.values()].filter((node) => node.visualParentPanelId === panelId); return direct.flatMap((node) => [node, ...this.descendants(node.panelInstanceId)]); }

  handlers() { return { folder: (panelId, folder) => this.openChild(panelId, folder), parent: (id) => this.openParent(id), close: (id) => this.closeNode(id), search: (id) => this.actions.localSearch?.(id),
    isolate: (id) => this.isolate(id), reattach: (id) => this.reattach(id), panelMenu: (id,x,y) => this.actions.panelMenu?.(id,x,y), newFolder: (id) => this.actions.newFolder?.(this.nodes.get(id)?.folderId),
    preview: (id, file) => this.preview(id, file), closePreview: (id) => this.closePreview(id), previewPage: (id, delta) => this.previewPage(id, delta), previewResized: (id) => this.previewResized(id),
    drag: (event, id) => this.startDrag(event, id), selectFolder: (id) => this.selectFolder(id), selectFile: (file, el) => this.selectFile(file, el), open: (id) => this.actions.open?.(id), rename: () => this.actions.rename?.(),
    drop: (event, id, region) => this.dropFilesystem(event, id, region) }; }

  async openChild(parentPanelId, folder) {
    const parent = this.nodes.get(parentPanelId), existing = this.panelForFolder(folder.id, parent.workingSetId);
    if (existing) { this.revealPanel(existing.panelInstanceId, folder.id); return; }
    const siblings = [...this.nodes.values()].filter((node) => node.visualParentPanelId === parentPanelId);
    const child = { ...folder, id: folder.id, folderId: folder.id, panelInstanceId: uid("panel"), workingSetId: parent.workingSetId,
      visualParentPanelId: parentPanelId, fsParentFolderId: parent.folderId, childrenLoaded: false,
      x: parent.x + (parent.renderedWidth || panelWidth(parent)) + 70, y: parent.y };
    this.nodes.set(child.panelInstanceId, child); await this.loadNode(child); this.layoutFamily(parentPanelId); this.render(); this.changed(); this.actions.visit?.(folder.id);
  }
  async openParent(childId) { const child=this.nodes.get(childId), folder=child?.compactParent; if(!child||!folder)return; const existing=this.panelForFolder(folder.id,child.workingSetId); if(existing){child.visualParentPanelId=existing.panelInstanceId;delete child.compactParent;this.layoutFamily(existing.panelInstanceId);this.render();this.changed();return;}
    const parent={...folder,id:folder.id,folderId:folder.id,panelInstanceId:uid("panel"),workingSetId:child.workingSetId,visualParentPanelId:null,fsParentFolderId:null,x:child.x,y:child.y,childrenLoaded:false};child.visualParentPanelId=parent.panelInstanceId;delete child.compactParent;this.nodes.set(parent.panelInstanceId,parent);await this.loadNode(parent);parent.x=child.x-panelWidth(parent)-70;this.layoutFamily(parent.panelInstanceId);this.render();this.changed(); }
  revealPanel(panelId, rowId = null) { const node = this.nodes.get(panelId); if (!node) return false; this.clearSelection(); this.selected = panelId; this.render();
    this.viewport.x = this.canvas.clientWidth / 2 - (node.x + (node.renderedWidth || panelWidth(node)) / 2) * this.viewport.zoom; this.viewport.y = this.canvas.clientHeight / 2 - (node.y + (node.renderedHeight || 160) / 2) * this.viewport.zoom; this.updateViewport();
    const row = rowId && this.elements.get(panelId)?.querySelector(`[data-id="${CSS.escape(rowId)}"]`); if (row) { row.classList.add("match-pulse"); setTimeout(() => row.classList.remove("match-pulse"), 1200); } return true; }
  revealNode(folderId) { const panel = [...this.nodes.values()].find((node) => node.folderId === folderId); return panel ? this.revealPanel(panel.panelInstanceId) : false; }
  moveBranchTo(panelId,x,y) { const root=this.nodes.get(panelId); if(!root)return; const dx=x-root.x,dy=y-root.y; for(const node of [root,...this.descendants(panelId)]){node.x+=dx;node.y+=dy;} }
  layoutFamily(parentId) { const parent=this.nodes.get(parentId),children=[...this.nodes.values()].filter(node=>node.visualParentPanelId===parentId).sort((a,b)=>a.x-b.x); if(!parent||!children.length)return;
    if(children.length===1){this.moveBranchTo(children[0].panelInstanceId,parent.x+(parent.renderedWidth||panelWidth(parent))+70,parent.y);return;} const gap=40,widths=children.map(child=>child.renderedWidth||panelWidth(child)),total=widths.reduce((sum,width)=>sum+width,0)+(children.length-1)*gap,start=parent.x+(parent.renderedWidth||panelWidth(parent))/2-total/2,y=parent.y+(parent.renderedHeight||220)+70;let x=start;children.forEach((child,index)=>{this.moveBranchTo(child.panelInstanceId,x,y);x+=widths[index]+gap;}); }
  async openSearchResult(originPanelId,item) { const origin=this.nodes.get(originPanelId),owner=item.parentFolder;if(!origin||!owner)return;let panel=this.panelForFolder(owner.id,origin.workingSetId);
    if(!panel){panel={...owner,id:owner.id,folderId:owner.id,panelInstanceId:uid("panel"),workingSetId:origin.workingSetId,visualParentPanelId:null,fsParentFolderId:null,x:origin.x,y:origin.y-260,childrenLoaded:false};this.nodes.set(panel.panelInstanceId,panel);await this.loadNode(panel);this.render();this.changed();}this.revealPanel(panel.panelInstanceId,item.id); }

  render() {
    this.updateViewport();
    for (const [id, element] of this.elements) if (!this.nodes.has(id)) { element.remove(); this.elements.delete(id); }
    const changedFamilies=new Set();
    for (const [id, node] of this.nodes) { let element = this.elements.get(id); if (!element) { element = createNodeElement(node, this.handlers()); this.elements.set(id, element); this.world.append(element); }
      const previousWidth=node.renderedWidth;element.style.width=`${panelWidth(node)}px`;updateNodeElement(element, node, id === this.selected, this.selectedItem?.id, new Set([...this.nodes.values()].filter((child) => child.visualParentPanelId === id).map((child) => child.folderId)), this.handlers());node.renderedWidth=element.offsetWidth;node.renderedHeight=element.offsetHeight;if(previousWidth!==undefined&&previousWidth!==node.renderedWidth){changedFamilies.add(id);if(node.visualParentPanelId)changedFamilies.add(node.visualParentPanelId);} }
    for(const parentId of changedFamilies)this.layoutFamily(parentId);if(changedFamilies.size)this.updatePositions();
    this.renderSets();this.renderEdges(); document.querySelector("#empty-hint").hidden = this.nodes.size > 0;
  }
  renderSets() {
    for (const [id, element] of this.setElements) if (!this.workingSets.has(id) || ![...this.nodes.values()].some((n) => n.workingSetId === id)) { element.remove(); this.setElements.delete(id); }
    for (const [id, set] of this.workingSets) { const members = [...this.nodes.values()].filter((n) => n.workingSetId === id); if (!members.length) continue;
      let el = this.setElements.get(id); if (!el) { el = document.createElement("section"); el.className = "working-set"; el.dataset.setId=id; el.addEventListener("pointerdown",event=>this.startSetDrag(event,id)); this.world.prepend(el); this.setElements.set(id, el); }
      const minX = Math.min(...members.map(n => n.x)) - 42, minY = Math.min(...members.map(n => n.y)) - 58, maxX = Math.max(...members.map(n => n.x + n.renderedWidth)) + 42, maxY = Math.max(...members.map(n => n.y + n.renderedHeight)) + 42;
      const style=this.dragSession?.type==="panel"&&this.dragSession.sourceSetId===id?this.dragSession.frozenStyle:{ transform: `translate(${minX}px,${minY}px)`, width: `${maxX-minX}px`, height: `${maxY-minY}px` }; Object.assign(el.style,style); }
  }
  renderEdges() { this.edges.replaceChildren();const canvasRect=this.canvas.getBoundingClientRect();for(const child of this.nodes.values()){const parent=this.nodes.get(child.visualParentPanelId);if(!parent)continue;const parentElement=this.elements.get(parent.panelInstanceId),childElement=this.elements.get(child.panelInstanceId),sourceRow=parentElement?.querySelector(`.folder-item[data-id="${CSS.escape(child.folderId)}"]`),header=childElement?.querySelector(".node-title");if(!sourceRow||!header)continue;const directChildren=[...this.nodes.values()].filter(node=>node.visualParentPanelId===parent.panelInstanceId),trail=directChildren.length===1,rowRect=sourceRow.getBoundingClientRect(),headerRect=header.getBoundingClientRect();const from=trail?{x:rowRect.right,y:rowRect.top+rowRect.height/2}:{x:rowRect.left+rowRect.width/2,y:rowRect.bottom},to=trail?{x:headerRect.left,y:headerRect.top+headerRect.height/2}:{x:headerRect.left+headerRect.width/2,y:headerRect.top};const source=this.screenToWorld(from.x-canvasRect.left,from.y-canvasRect.top),target=this.screenToWorld(to.x-canvasRect.left,to.y-canvasRect.top),exit=trail?{x:source.x+18,y:source.y}:{x:source.x,y:source.y+18},approach=trail?{x:target.x-18,y:target.y}:{x:target.x,y:target.y-18},mx=(exit.x+approach.x)/2,my=(exit.y+approach.y)/2;const path=document.createElementNS("http://www.w3.org/2000/svg","path");path.setAttribute("d",`M ${source.x} ${source.y} L ${exit.x} ${exit.y} C ${trail?mx:exit.x} ${trail?exit.y:my}, ${trail?mx:approach.x} ${trail?approach.y:my}, ${approach.x} ${approach.y} L ${target.x} ${target.y}`);this.edges.append(path);}}

  isolate(panelId) { const root = this.nodes.get(panelId),parent=this.nodes.get(root?.visualParentPanelId); if (!root || !parent) return false; const setId = this.newSet(); root.compactParent={id:parent.folderId,name:parent.name,path:parent.path,kind:"folder"};root.fsParentFolderId=parent.folderId;root.visualParentPanelId = null; for (const node of [root, ...this.descendants(panelId)]) node.workingSetId = setId; this.cleanupSets(); this.render(); this.changed();return true; }
  reattach(panelId, destinationSetId = null) { const root = this.nodes.get(panelId); if (!root || root.visualParentPanelId || !root.fsParentFolderId) return false;
    const parent = [...this.nodes.values()].find((node) => node.folderId === root.fsParentFolderId && node.workingSetId !== root.workingSetId && (!destinationSetId || node.workingSetId === destinationSetId)); if (!parent) return false;
    if (this.panelForFolder(root.folderId, parent.workingSetId)) return false; const old = root.workingSetId; root.visualParentPanelId = parent.panelInstanceId; delete root.compactParent;
    for (const node of [root, ...this.descendants(panelId)]) node.workingSetId = parent.workingSetId; this.layoutFamily(parent.panelInstanceId); this.workingSets.delete(old); this.render(); this.changed(); return true; }
  cleanupSets() { for (const id of [...this.workingSets.keys()]) if (![...this.nodes.values()].some(n => n.workingSetId === id)) this.workingSets.delete(id); }
  removeBranch(panelId) { const removed=[this.nodes.get(panelId),...this.descendants(panelId)].filter(Boolean);if(removed.some(node=>node.panelInstanceId===this.selected||node.folderId===this.selectedItem?.parentId))this.clearSelection();for(const node of removed)this.nodes.delete(node.panelInstanceId); }
  closeNode(panelId) { this.removeBranch(panelId); this.cleanupSets(); this.clearSelection(); this.render(); this.changed(); }

  dropFilesystem(event, destinationFolderId, region) { const kind=event.dataTransfer.getData("application/x-nodefilemanager-kind"), id=event.dataTransfer.getData("application/x-nodefilemanager-item"); if (!id || kind !== region) return; this.actions.transfer?.(id, destinationFolderId, event.altKey, kind); }
  preview(panelId, file) { const node=this.nodes.get(panelId); if (![".pdf",".jpg",".jpeg",".png"].includes((file.extension||"").toLowerCase())) { if(node?.preview)this.closePreview(panelId); return; } node.preview={...file,page:1}; this.updatePreview(panelId); this.changed(); }
  closePreview(id){const n=this.nodes.get(id);if(!n)return;delete n.preview;this.updatePreview(id);this.changed();} previewPage(id,d){const p=this.nodes.get(id)?.preview;if(!p)return;p.page=Math.max(1,p.page+d);this.updatePreview(id);}
  updatePreview(id){const n=this.nodes.get(id),e=this.elements.get(id);if(n&&e)updatePreviewElement(e,n,this.handlers());} previewResized(id){const n=this.nodes.get(id),e=this.elements.get(id);if(n&&e)n.renderedHeight=e.offsetHeight;this.renderSets();}
  selectFolder(id){this.clearSelection();this.selected=id;this.elements.get(id)?.classList.add("selected");} selectFile(file,el){this.clearSelection();this.selectedItem=file;el.classList.add("selected");}
  clearSelection(){this.world.querySelector(".file-item.selected")?.classList.remove("selected");if(this.selected)this.elements.get(this.selected)?.classList.remove("selected");this.selected=null;this.selectedItem=null;}
  updateFavoriteStates() {}
  visibleFolders(){return [...this.nodes.values()];}
  async refresh(folderId=null){const targets=folderId?[...this.nodes.values()].filter(node=>node.folderId===folderId):[...this.nodes.values()].filter(node=>!node.visualParentPanelId);for(const node of targets)await this.refreshBranch(node);this.cleanupSets();this.render();this.changed();}
  async refreshBranch(node){if(!this.nodes.has(node.panelInstanceId))return;let contents;try{contents=await this.loadChildren(node.folderId);}catch(error){if(node.visualParentPanelId){this.removeBranch(node.panelInstanceId);return;}throw error;}node.folders=contents.folders;node.files=contents.files;node.childrenLoaded=true;const available=new Set(contents.folders.map(folder=>folder.id));for(const child of [...this.nodes.values()].filter(panel=>panel.visualParentPanelId===node.panelInstanceId))if(!available.has(child.folderId))this.removeBranch(child.panelInstanceId);for(const child of [...this.nodes.values()].filter(panel=>panel.visualParentPanelId===node.panelInstanceId))await this.refreshBranch(child);}
  async applyRename(oldId,item){if(item.kind!=="folder")return;await this.reconcileFolderIdentity(oldId,item,false);}
  async reconcileMovedFolder(oldFolderId,movedItem) { await this.reconcileFolderIdentity(oldFolderId,movedItem,true); }
  async reconcileFolderIdentity(oldFolderId,item,reconnect) { const roots=[...this.nodes.values()].filter(node=>node.folderId===oldFolderId);if(!roots.length)return;const parentResponse=reconnect?await this.actions.getParent?.(item.id):null,parentMetadata=parentResponse?.parent||null;
    for(const root of roots){Object.assign(root,{id:item.id,folderId:item.id,name:item.name,path:item.path,fsParentFolderId:item.parentId});if(reconnect){const normalParent=this.panelForFolder(item.parentId,root.workingSetId);if(normalParent){root.visualParentPanelId=normalParent.panelInstanceId;delete root.compactParent;}else{root.visualParentPanelId=null;root.compactParent=parentMetadata;}}await this.reconcileVisibleDescendants(root);}this.render();this.changed();}
  async reconcileVisibleDescendants(parent) { const contents=await this.loadChildren(parent.folderId);parent.folders=contents.folders;parent.files=contents.files;parent.childrenLoaded=true;if(parent.preview){const preview=contents.files.find(file=>file.name===parent.preview.name);if(preview)parent.preview={...parent.preview,...preview};else delete parent.preview;}const children=[...this.nodes.values()].filter(node=>node.visualParentPanelId===parent.panelInstanceId);for(const child of children){const current=contents.folders.find(folder=>folder.name===child.name);if(!current)continue;Object.assign(child,{id:current.id,folderId:current.id,name:current.name,path:current.path,fsParentFolderId:parent.folderId});delete child.compactParent;await this.reconcileVisibleDescendants(child);} }

  startDrag(event,id){if(event.button!==0||event.target.closest("button,.file-item,.folder-item,input,iframe"))return;this.finishDrag(false);const root=this.nodes.get(id),setElement=this.setElements.get(root?.workingSetId);if(!root||!setElement)return;const members=[root,...this.descendants(id)],origins=new Map(members.map(n=>[n.panelInstanceId,{x:n.x,y:n.y}]));this.dragSession={type:"panel",pointerId:event.pointerId,nodeId:id,sourceSetId:root.workingSetId,element:event.currentTarget,startX:event.clientX,startY:event.clientY,origins,dragging:false,frozenRect:setElement.getBoundingClientRect(),frozenStyle:{transform:setElement.style.transform,width:setElement.style.width,height:setElement.style.height}};event.currentTarget.setPointerCapture(event.pointerId);}
  startSetDrag(event,setId){if(event.button!==0)return;this.finishDrag(false);event.stopPropagation();const members=[...this.nodes.values()].filter(n=>n.workingSetId===setId),origins=new Map(members.map(n=>[n.panelInstanceId,{x:n.x,y:n.y}]));this.dragSession={type:"set",pointerId:event.pointerId,element:event.currentTarget,startX:event.clientX,startY:event.clientY,origins,dragging:false};event.currentTarget.setPointerCapture(event.pointerId);}
  dragIntent(session,x,y){if(session.type!=="panel")return null;const root=this.nodes.get(session.nodeId),target=document.elementsFromPoint(x,y).map(element=>element.closest?.('[data-drop-kind="folder"]')).find(element=>element&&element.closest(".folder-node")?.dataset.id!==session.nodeId);
    if(target)return{type:"filesystem",destinationId:target.dataset.destinationId};const destination=[...this.setElements].find(([setId,element])=>setId!==session.sourceSetId&&(()=>{const r=element.getBoundingClientRect();return x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom;})());
    if(destination&&[...this.nodes.values()].some(n=>n.workingSetId===destination[0]&&n.folderId===root.fsParentFolderId))return{type:"reattach",setId:destination[0]};const r=session.frozenRect;if(root.visualParentPanelId&&(x<r.left||x>r.right||y<r.top||y>r.bottom))return{type:"isolate"};return null;}
  continueDrag(event){const s=this.dragSession;if(!s||s.pointerId!==event.pointerId)return;const dx=event.clientX-s.startX,dy=event.clientY-s.startY;if(!s.dragging&&Math.hypot(dx,dy)<5)return;if(!s.dragging&&s.type==="panel")this.selectFolder(s.nodeId);s.dragging=true;if(s.type==="set")for(const[id,o]of s.origins){const n=this.nodes.get(id);if(n){n.x=o.x+dx/this.viewport.zoom;n.y=o.y+dy/this.viewport.zoom;}}if(s.type==="panel")this.canvas.dataset.dragIntent=this.dragIntent(s,event.clientX,event.clientY)?.type||"return";this.updatePositions();this.renderSets();this.renderEdges();}
  endDrag(event){const s=this.dragSession;if(!s||s.pointerId!==event.pointerId)return;const intent=this.dragIntent(s,event.clientX,event.clientY),moved=s.dragging,id=s.nodeId;if(!moved){this.finishDrag(true);if(id)this.selectFolder(id);return;}if(s.type==="set"){this.finishDrag(true);return;}if(intent?.type==="filesystem"){const folderId=this.nodes.get(id).folderId;this.finishDrag(false);this.actions.transfer?.(folderId,intent.destinationId,false,"folder");return;}this.finishDrag(Boolean(intent));if(intent?.type==="isolate")this.isolate(id);else if(intent?.type==="reattach")this.reattach(id,intent.setId);}
  cancelDrag(event){if(this.dragSession?.pointerId===event.pointerId)this.finishDrag(false);} finishDrag(save){const s=this.dragSession;if(!s)return;this.dragSession=null;delete this.canvas.dataset.dragIntent;if(s.element.hasPointerCapture?.(s.pointerId))s.element.releasePointerCapture(s.pointerId);if(save&&s.dragging)this.changed();else if(s.dragging){for(const[id,o]of s.origins){const n=this.nodes.get(id);if(n)Object.assign(n,o);}this.updatePositions();this.renderSets();this.renderEdges();}}
  updatePositions(){for(const[id,el]of this.elements){const n=this.nodes.get(id);if(n)el.style.transform=`translate(${n.x}px,${n.y}px)`;}} updateViewport(){applyViewport(this.world,this.canvas.querySelector("#edges"),this.viewport);}
  escape(event){const active=this.dragSession||this.selected||this.selectedItem||this.actions.dialogOpen?.();this.finishDrag(false);this.clearSelection();this.actions.cancelDialog?.();if(active)event.preventDefault();}
  startPan(event){if(event.target.closest?.(".folder-node,.working-set")||event.button!==0)return;this.canvas.setPointerCapture(event.pointerId);this.canvas.classList.add("panning");const sx=event.clientX,sy=event.clientY,x=this.viewport.x,y=this.viewport.y;const move=e=>{this.viewport.x=x+e.clientX-sx;this.viewport.y=y+e.clientY-sy;this.updateViewport();};const end=()=>{this.canvas.removeEventListener("pointermove",move);this.canvas.classList.remove("panning");this.changed();};this.canvas.addEventListener("pointermove",move);this.canvas.addEventListener("pointerup",end,{once:true});}
  zoom(event){event.preventDefault();const r=this.canvas.getBoundingClientRect(),sx=event.clientX-r.left,sy=event.clientY-r.top,old=this.viewport.zoom,next=Math.min(2.5,Math.max(.25,old*Math.exp(-event.deltaY*.001)));this.viewport.x=sx-(sx-this.viewport.x)*next/old;this.viewport.y=sy-(sy-this.viewport.y)*next/old;this.viewport.zoom=next;this.updateViewport();this.changed();}
  screenToWorld(x,y){return{x:(x-this.viewport.x)/this.viewport.zoom,y:(y-this.viewport.y)/this.viewport.zoom};} changed(){this.onChange(this.serialize());}
  serialize(){const nodes=Object.fromEntries([...this.nodes].map(([id,n])=>{const{childrenLoaded,folders,files,preview,renderedWidth,renderedHeight,compactParent,...saved}=n;return[id,saved];}));const roots=[...this.nodes.values()].filter(n=>!n.visualParentPanelId).map(({folderId,panelInstanceId,workingSetId,path})=>({id:folderId,panelInstanceId,workingSetId,path}));return{version:2,roots,nodes,workingSets:Object.fromEntries(this.workingSets),viewport:this.viewport};}
}
