import { activateSearch, cancelFolderBrowser, confirmFolderBrowser, copyItem, createFolder, getChildren, getHealth, getNavigation, getParent, moveItem, navigateFolderBrowser, openFile, openNavigation, quitApplication, removeFavorite, renameItem, searchFolder, searchNames, startFolderBrowser, toggleFavorite, visitFolder } from "./api/client.js";
import { FolderCanvas } from "./canvas/canvas.js";
import { createWorkspaceSaver, restoreWorkspace } from "./workspace/workspace.js";
import { createIcon } from "./icons.js";

const status = document.querySelector("#status");
const showError = (error) => { console.error(error); status.textContent = error.message || String(error); };
const save = createWorkspaceSaver(showError);
const canvas = new FolderCanvas(document.querySelector("#canvas"), save, async (id) => {
  status.textContent = "子フォルダーを読み込んでいます…";
  try { const result = await getChildren(id); status.textContent = `${result.folders.length} フォルダー / ${result.files.length} ファイル`; return result; }
  catch (error) { showError(error); throw error; }
});
function renderNavigation(state) {
  const locationKey = (path) => navigator.userAgent.includes("Windows") ? path.toLocaleLowerCase() : path;
  const favoritePaths = new Set(state.favorites.map((item) => locationKey(item.path)));
  canvas.updateFavoriteStates(favoritePaths, locationKey);
  const chips = (items, favorite) => items.map((item) => { const chip = document.createElement("span"); chip.className = `quick-chip${item.available ? "" : " unavailable"}`; chip.title = item.path;
    const open = document.createElement("button"); open.type = "button"; open.className = "quick-remove"; open.style.padding = "0"; open.textContent = item.name; open.disabled = !item.available; open.addEventListener("click", () => navigateEntry(item.id)); chip.append(open);
    if (favorite) { const remove = document.createElement("button"); remove.type = "button"; remove.className = "quick-remove"; remove.setAttribute("aria-label", "Favorite を削除"); remove.title = "Favorite を削除"; remove.append(createIcon("close")); remove.addEventListener("click", async () => renderNavigation(await removeFavorite(item.id))); chip.append(remove); } return chip; });
  document.querySelector("#favorites")?.replaceChildren(...chips(state.favorites, true)); document.querySelector("#hot").replaceChildren(...chips(state.hot, false));
}
async function navigateEntry(id) { try { const result = await openNavigation(id); renderNavigation(result); if (!canvas.revealNode(result.folder.id)) await canvas.addRoot(result.folder); status.textContent = `移動: ${result.folder.path}`; } catch (error) { showError(error); renderNavigation(await getNavigation()); } }
canvas.actions.favorite = async (id) => { try { renderNavigation(await toggleFavorite(id)); } catch (error) { showError(error); } };
canvas.actions.getParent = getParent;
canvas.actions.visit = async (id) => { try { renderNavigation(await visitFolder(id)); } catch (error) { showError(error); } };

async function refresh() { try { await canvas.refresh(); status.textContent = "ファイルシステムから更新しました"; } catch (error) { showError(error); } }
canvas.actions.open = async (id) => { try { await openFile(id); status.textContent = "ファイルを開きました"; } catch (error) { showError(error); } };
let renameTarget=null;const renameDialog=document.querySelector("#rename-dialog");canvas.actions.rename=()=>{renameTarget=canvas.selectedItem||canvas.nodes.get(canvas.selected);if(!renameTarget)return;document.querySelector("#rename-name").value=renameTarget.name;renameDialog.showModal();document.querySelector("#rename-name").select();};document.querySelector("#rename-confirm").addEventListener("click",async event=>{event.preventDefault();const item=renameTarget,name=document.querySelector("#rename-name").value;if(!item||name===item.name){renameDialog.close("cancel");return;}try{const result=await renameItem(item.id,name);await canvas.applyRename(item.id,result.item);canvas.selectedItem=null;renameDialog.close("confirm");renderNavigation(await getNavigation());await refresh();}catch(error){showError(error);}});renameDialog.addEventListener("close",()=>{renameTarget=null;});
canvas.actions.transfer = async (id, destinationId, copy = false, kind = "file") => { try { const movedPanel=kind==="folder"?[...canvas.nodes.values()].find(node=>node.folderId===id):null, sourceId = canvas.selectedItem?.parentId || canvas.nodes.get(movedPanel?.visualParentPanelId)?.folderId || movedPanel?.fsParentFolderId; const result=await (copy ? copyItem : moveItem)(id, destinationId);if(!copy&&kind==="folder")await canvas.reconcileMovedFolder(id,result.item);canvas.clearSelection(); if (!copy) renderNavigation(await getNavigation()); if (sourceId) await canvas.refresh(sourceId); if (destinationId !== sourceId) await canvas.refresh(destinationId); status.textContent = copy ? "コピーしました" : "移動しました"; } catch (error) { showError(error); } };

document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#rename").addEventListener("click", () => canvas.actions.rename());
const browserDialog = document.querySelector("#folder-browser-dialog"), newFolderDialog = document.querySelector("#new-folder-dialog"); let browserSession = null, browserGeneration = 0, newFolderParent = null;
const browserButton = (label, id, icon = null) => { const button = document.createElement("button"); button.type = "button"; button.textContent = label; if (icon) button.prepend(createIcon(icon)); button.addEventListener("click", () => navigateBrowser(id)); return button; };
function showBrowser(view) {
  browserSession = view.sessionId; document.querySelector(".folder-browser-path").textContent = view.current.path;
  const locations = view.locations.map((item) => browserButton(item.name, item.id)); if (view.parentId) locations.push(browserButton("Up", view.parentId, "up"));
  document.querySelector(".folder-browser-locations").replaceChildren(...locations);
  document.querySelector(".folder-browser-folders").replaceChildren(...view.folders.map((item) => browserButton(item.name, item.id, "folder")));
}
async function navigateBrowser(id) { try { showBrowser(await navigateFolderBrowser(browserSession, id)); } catch (error) { showError(error); } }
canvas.actions.dialogOpen = () => browserDialog.open || newFolderDialog.open || renameDialog.open;
canvas.actions.cancelDialog = () => { if (browserDialog.open) browserDialog.close("cancel"); if (newFolderDialog.open) newFolderDialog.close("cancel"); if (renameDialog.open) renameDialog.close("cancel"); };
canvas.actions.newFolder = (parentId) => { newFolderParent = parentId; document.querySelector("#new-folder-name").value = ""; newFolderDialog.showModal(); document.querySelector("#new-folder-name").focus(); };
document.querySelector("#new-folder-confirm").addEventListener("click", async (event) => {
  event.preventDefault(); const name = document.querySelector("#new-folder-name").value;
  try { await createFolder(newFolderParent, name); newFolderDialog.close("confirm"); await canvas.refresh(newFolderParent); status.textContent = `フォルダーを作成しました: ${name}`; } catch (error) { showError(error); }
});

try {
  const health = await getHealth();
  document.querySelector("#build-identity").textContent = `v${health.version} · ${health.packaged ? "packaged" : "source"}${health.commit !== "unknown" ? ` · ${health.commit.slice(0, 8)}` : ""}`;
  const quit = document.querySelector("#quit");
  if (health.packaged) { quit.hidden = false; quit.addEventListener("click", async () => {
    status.textContent = "ワークスペースを保存しています…";
    try { await save.flush(); status.textContent = "終了しています…"; await quitApplication(); }
    catch (error) { showError(error); }
  }); }
  status.textContent = await restoreWorkspace(canvas); renderNavigation(await getNavigation());
} catch (error) { showError(error); }

async function selectFolder() {
  const generation = ++browserGeneration; browserDialog.returnValue = "cancel"; browserDialog.showModal(); status.textContent = "フォルダーを読み込んでいます…";
  try {
    const view = await startFolderBrowser();
    if (!browserDialog.open || generation !== browserGeneration) { cancelFolderBrowser(view.sessionId).catch(showError); return; }
    showBrowser(view); status.textContent = "フォルダーを選択してください";
  } catch (error) { if (browserDialog.open) browserDialog.close("cancel"); showError(error); }
}
document.querySelector("#folder-browser-confirm").addEventListener("click", async (event) => {
  event.preventDefault(); if (!browserSession) return;
  try { const session = browserSession; browserSession = null; const result = await confirmFolderBrowser(session); browserDialog.close("confirm"); await canvas.addRoot(result.folder); renderNavigation(result); status.textContent = `追加: ${result.folder.path}`; } catch (error) { showError(error); }
});
browserDialog.addEventListener("click", (event) => { if (event.target === browserDialog) browserDialog.close("cancel"); });
browserDialog.addEventListener("close", () => { browserGeneration += 1; const session = browserSession; browserSession = null; if (session) cancelFolderBrowser(session).catch(showError); });

let focusRefreshTimer;
function refreshAfterFocus() { clearTimeout(focusRefreshTimer); focusRefreshTimer = setTimeout(() => { if (canvas.nodes.size && !document.hidden) refresh(); }, 350); }
window.addEventListener("focus", refreshAfterFocus);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshAfterFocus(); });

let temporarySearch;
function showResults(panel, results, query) {
  temporarySearch?.remove(); const card=document.createElement("section"); card.className="temporary-search";
  card.style.transform=`translate(${panel.x}px,${panel.y-170}px)`; const title=document.createElement("strong"); title.textContent=`Search: ${query}`; card.append(title);
  for(const item of results){const button=document.createElement("button");button.textContent=item.name;button.onclick=async()=>{const owner=[...canvas.nodes.values()].find(n=>(n.files||[]).some(x=>x.id===item.id)||(n.folders||[]).some(x=>x.id===item.id));if(owner)canvas.revealPanel(owner.panelInstanceId,item.id);else await canvas.openSearchResult(panel.panelInstanceId,item);card.remove();};card.append(button);} canvas.world.append(card);temporarySearch=card;
}
canvas.actions.localSearch = (panelId) => { const panel=canvas.nodes.get(panelId), input=document.createElement("input"); input.className="header-search";input.type="search";input.placeholder="Search recursively…";canvas.elements.get(panelId).querySelector(".node-title").append(input);input.focus();let timer;
  input.oninput=()=>{clearTimeout(timer);const q=input.value.trim();if(q.length<2)return;timer=setTimeout(async()=>{try{const response=await searchFolder(panel.folderId,q);showResults(panel,response.results,q);status.textContent=`${response.results.length} 件${response.truncated?"（検索上限）":""}`;}catch(error){showError(error);}},300);};input.onkeydown=e=>{if(e.key==="Escape"){temporarySearch?.remove();input.remove();canvas.canvas.focus();}};input.onblur=()=>{if(!input.value)input.remove();}; };
function workspaceSearch(){const query=prompt("Search visible workspace");if(!query)return;const term=query.toLocaleLowerCase(), matches=[];for(const panel of canvas.nodes.values())for(const item of [...(panel.folders||[]),...(panel.files||[])])if(item.name.toLocaleLowerCase().includes(term))matches.push(item);const anchor=[...canvas.nodes.values()][0];if(anchor)showResults(anchor,matches,query);status.textContent=`${matches.length} visible matches`;}
const menu=document.querySelector("#canvas-menu");canvas.actions.canvasMenu=(x,y)=>{menu.style.left=`${x}px`;menu.style.top=`${y}px`;menu.hidden=false;};
menu.addEventListener("click",e=>{const action=e.target.dataset.action;menu.hidden=true;if(action==="select")selectFolder();if(action==="search")workspaceSearch();});document.addEventListener("pointerdown",e=>{if(!e.target.closest("#canvas-menu"))menu.hidden=true;});
const panelMenu=document.querySelector("#panel-menu");let panelMenuId=null;canvas.actions.panelMenu=(id,x,y)=>{panelMenuId=id;const node=canvas.nodes.get(id);panelMenu.querySelector('[data-action="isolate"]').hidden=!node?.visualParentPanelId;panelMenu.style.left=`${x}px`;panelMenu.style.top=`${y}px`;panelMenu.hidden=false;};panelMenu.addEventListener("click",event=>{const action=event.target.dataset.action,id=panelMenuId;panelMenu.hidden=true;if(action==="isolate")canvas.isolate(id);if(action==="rename")canvas.actions.rename();if(action==="new")canvas.actions.newFolder(canvas.nodes.get(id)?.folderId);});document.addEventListener("pointerdown",event=>{if(!event.target.closest("#panel-menu"))panelMenu.hidden=true;});
document.addEventListener("keydown",event=>{if(event.key==="Escape"){temporarySearch?.remove();menu.hidden=true;}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==="k"){event.preventDefault();workspaceSearch();}},true);
