import { loadWorkspace, saveWorkspace } from "../api/client.js";

export async function restoreWorkspace(canvas) {
  const { state, availableRoots } = await loadWorkspace();
  await canvas.restore(state, availableRoots);
  const missing = (state.roots || []).length - availableRoots.length;
  return missing > 0 ? `${missing} 件の保存済みルートを復元できませんでした` : "ワークスペースを復元しました";
}

export function createWorkspaceSaver(reportError) {
  let timer;
  return (state) => {
    clearTimeout(timer);
    timer = setTimeout(() => saveWorkspace(state).catch(reportError), 250);
  };
}
