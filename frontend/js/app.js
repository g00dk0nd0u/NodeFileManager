import { cancelFolderBrowser, confirmFolderBrowser, copyItem, createFolder, getChildren, getHealth, moveItem, navigateFolderBrowser, openFile, quitApplication, renameItem, startFolderBrowser } from "./api/client.js";
import { FolderCanvas } from "./canvas/canvas.js";
import { createWorkspaceSaver, restoreWorkspace } from "./workspace/workspace.js";

const status = document.querySelector("#status");
const showError = (error) => { console.error(error); status.textContent = error.message || String(error); };
const save = createWorkspaceSaver(showError);
const canvas = new FolderCanvas(document.querySelector("#canvas"), save, async (id) => {
  status.textContent = "子フォルダーを読み込んでいます…";
  try { const result = await getChildren(id); status.textContent = `${result.folders.length} フォルダー / ${result.files.length} ファイル`; return result; }
  catch (error) { showError(error); throw error; }
});

async function refresh() { try { await canvas.refresh(); status.textContent = "ファイルシステムから更新しました"; } catch (error) { showError(error); } }
canvas.actions.open = async (id) => { try { await openFile(id); status.textContent = "ファイルを開きました"; } catch (error) { showError(error); } };
canvas.actions.rename = async () => {
  const item = canvas.selectedItem || canvas.nodes.get(canvas.selected); if (!item) return;
  const name = prompt("新しい名前（同じフォルダー内）", item.name); if (name === null || name === item.name) return;
  try { const result = await renameItem(item.id, name); await canvas.applyRename(item.id, result.item); canvas.selectedItem = null; await refresh(); } catch (error) { showError(error); }
};
canvas.actions.transfer = async (id, destinationId, copy = false) => { try { const sourceId = canvas.selectedItem?.parentId; await (copy ? copyItem : moveItem)(id, destinationId); canvas.clearSelection(); if (sourceId) await canvas.refresh(sourceId); if (destinationId !== sourceId && canvas.nodes.has(destinationId)) await canvas.refresh(destinationId); status.textContent = copy ? "コピーしました" : "移動しました"; } catch (error) { showError(error); } };

document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#rename").addEventListener("click", () => canvas.actions.rename());
const browserDialog = document.querySelector("#folder-browser-dialog"), newFolderDialog = document.querySelector("#new-folder-dialog"); let browserSession = null, browserGeneration = 0, newFolderParent = null;
const browserButton = (label, id) => { const button = document.createElement("button"); button.type = "button"; button.textContent = label; button.addEventListener("click", () => navigateBrowser(id)); return button; };
function showBrowser(view) {
  browserSession = view.sessionId; document.querySelector(".folder-browser-path").textContent = view.current.path;
  const locations = view.locations.map((item) => browserButton(item.name, item.id)); if (view.parentId) locations.push(browserButton("↑ Up", view.parentId));
  document.querySelector(".folder-browser-locations").replaceChildren(...locations);
  document.querySelector(".folder-browser-folders").replaceChildren(...view.folders.map((item) => browserButton(`📁 ${item.name}`, item.id)));
}
async function navigateBrowser(id) { try { showBrowser(await navigateFolderBrowser(browserSession, id)); } catch (error) { showError(error); } }
canvas.actions.dialogOpen = () => browserDialog.open || newFolderDialog.open;
canvas.actions.cancelDialog = () => { if (browserDialog.open) browserDialog.close("cancel"); if (newFolderDialog.open) newFolderDialog.close("cancel"); };
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
  status.textContent = await restoreWorkspace(canvas);
} catch (error) { showError(error); }

const selectFolderButton = document.querySelector("#select-folder");
selectFolderButton.addEventListener("click", async () => {
  const generation = ++browserGeneration; browserDialog.returnValue = "cancel"; browserDialog.showModal(); status.textContent = "フォルダーを読み込んでいます…";
  try {
    const view = await startFolderBrowser();
    if (!browserDialog.open || generation !== browserGeneration) { cancelFolderBrowser(view.sessionId).catch(showError); return; }
    showBrowser(view); status.textContent = "フォルダーを選択してください";
  } catch (error) { if (browserDialog.open) browserDialog.close("cancel"); showError(error); }
});
document.querySelector("#folder-browser-confirm").addEventListener("click", async (event) => {
  event.preventDefault(); if (!browserSession) return;
  try { const session = browserSession; browserSession = null; const { folder } = await confirmFolderBrowser(session); browserDialog.close("confirm"); await canvas.addRoot(folder); status.textContent = `追加: ${folder.path}`; } catch (error) { showError(error); }
});
browserDialog.addEventListener("click", (event) => { if (event.target === browserDialog) browserDialog.close("cancel"); });
browserDialog.addEventListener("close", () => { browserGeneration += 1; const session = browserSession; browserSession = null; if (session) cancelFolderBrowser(session).catch(showError); });

let focusRefreshTimer;
function refreshAfterFocus() { clearTimeout(focusRefreshTimer); focusRefreshTimer = setTimeout(() => { if (canvas.nodes.size && !document.hidden) refresh(); }, 350); }
window.addEventListener("focus", refreshAfterFocus);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshAfterFocus(); });
