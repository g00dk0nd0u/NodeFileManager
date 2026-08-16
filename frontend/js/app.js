import { getChildren, getHealth, selectFolder } from "./api/client.js";
import { FolderCanvas } from "./canvas/canvas.js";
import { createWorkspaceSaver, restoreWorkspace } from "./workspace/workspace.js";

const status = document.querySelector("#status");
const showError = (error) => { console.error(error); status.textContent = error.message || String(error); };
const save = createWorkspaceSaver(showError);
const canvas = new FolderCanvas(document.querySelector("#canvas"), save, async (id) => {
  status.textContent = "子フォルダーを読み込んでいます…";
  try { const result = await getChildren(id); status.textContent = `${result.folders.length} 件の子フォルダー`; return result.folders; }
  catch (error) { showError(error); throw error; }
});

try {
  await getHealth();
  status.textContent = await restoreWorkspace(canvas);
} catch (error) { showError(error); }

document.querySelector("#select-folder").addEventListener("click", async (event) => {
  event.currentTarget.disabled = true; status.textContent = "フォルダー選択を待っています…";
  try {
    const { folder } = await selectFolder();
    if (folder) { canvas.addRoot(folder); status.textContent = `追加: ${folder.path}`; }
    else status.textContent = "フォルダー選択をキャンセルしました";
  } catch (error) { showError(error); }
  finally { event.currentTarget.disabled = false; }
});
