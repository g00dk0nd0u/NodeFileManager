import { copyItem, getChildren, getHealth, moveItem, openFile, renameItem, selectFolder } from "./api/client.js";
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
  try { const result = await renameItem(item.id, name); canvas.applyRename(item.id, result.item); canvas.selectedItem = null; await refresh(); } catch (error) { showError(error); }
};
canvas.actions.transfer = async (id, destinationId, copy = false) => { try { await (copy ? copyItem : moveItem)(id, destinationId); await refresh(); status.textContent = copy ? "コピーしました" : "移動しました"; } catch (error) { showError(error); } };

document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#rename").addEventListener("click", () => canvas.actions.rename());
const destinationDialog = document.querySelector("#destination-dialog");
const destinationSelect = document.querySelector("#destination-folder");
let pendingTransfer = null;
for (const [button, copy] of [["#copy", true], ["#move", false]]) document.querySelector(button).addEventListener("click", () => {
  const item = canvas.selectedItem || canvas.nodes.get(canvas.selected); if (!item) return;
  const folders = canvas.visibleFolders(); destinationSelect.replaceChildren(...folders.map((folder) => new Option(folder.path, folder.id)));
  if (!folders.length) { status.textContent = "移動先として使える表示中フォルダーがありません"; return; }
  pendingTransfer = { itemId: item.id, copy, destinationIds: new Set(folders.map((folder) => folder.id)) };
  document.querySelector("#destination-label").textContent = copy ? "コピー先フォルダー" : "移動先フォルダー";
  document.querySelector("#destination-confirm").textContent = copy ? "コピー" : "移動";
  destinationDialog.returnValue = "cancel";
  status.textContent = copy ? "コピー先フォルダーを選択してください" : "移動先フォルダーを選択してください"; destinationDialog.showModal();
});
destinationDialog.addEventListener("close", () => {
  const transfer = pendingTransfer; pendingTransfer = null;
  if (destinationDialog.returnValue !== "confirm") { status.textContent = "操作をキャンセルしました"; return; }
  const destinationId = destinationSelect.value;
  if (!transfer?.destinationIds.has(destinationId)) { status.textContent = "有効な移動先が選択されていません"; return; }
  canvas.actions.transfer(transfer.itemId, destinationId, transfer.copy);
});

try {
  await getHealth();
  status.textContent = await restoreWorkspace(canvas);
} catch (error) { showError(error); }

const selectFolderButton = document.querySelector("#select-folder");
selectFolderButton.addEventListener("click", async () => {
  selectFolderButton.disabled = true; status.textContent = "フォルダー選択を待っています…";
  try {
    const { folder } = await selectFolder();
    if (folder) { canvas.addRoot(folder); status.textContent = `追加: ${folder.path}`; }
    else status.textContent = "フォルダー選択をキャンセルしました";
  } catch (error) { showError(error); }
  finally { selectFolderButton.disabled = false; }
});
