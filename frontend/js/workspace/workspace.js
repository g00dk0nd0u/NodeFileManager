import { loadWorkspace, saveWorkspace } from "../api/client.js";

export async function restoreWorkspace(canvas) {
  const { state, availableRoots } = await loadWorkspace();
  await canvas.restore(state, availableRoots);
  const missing = (state.roots || []).length - availableRoots.length;
  return missing > 0 ? `${missing} 件の保存済みルートを復元できませんでした` : "ワークスペースを復元しました";
}

export function createWorkspaceSaver(reportError) {
  let timer, latestState, pending = Promise.resolve();
  const persist = () => {
    timer = undefined;
    pending = pending.catch(() => {}).then(() => saveWorkspace(latestState));
    return pending;
  };
  const save = (state) => {
    latestState = state;
    clearTimeout(timer);
    timer = setTimeout(() => persist().catch(reportError), 250);
  };
  save.flush = async () => {
    clearTimeout(timer);
    timer = undefined;
    if (latestState !== undefined) await persist();
    else await pending;
  };
  return save;
}
