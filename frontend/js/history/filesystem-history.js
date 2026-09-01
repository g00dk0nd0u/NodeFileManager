export function recordFilesystemOperation(history, { label, token, initialId, replay, reconcile, reportError }) {
  let currentId = initialId;
  const bestEffortReconcile = async (result) => {
    const previousId = currentId;
    currentId = result.item.id;
    try { await reconcile(result, previousId); }
    catch (error) { reportError(error); }
  };
  const apply = async (direction) => {
    const previousId = currentId;
    const result = await replay(token, direction);
    currentId = result.item.id;
    try { await reconcile(result, previousId); }
    catch (error) { reportError(error); }
  };
  history.record({ label, undo: () => apply("undo"), redo: () => apply("redo") });
  return { reconcileInitial: bestEffortReconcile };
}
