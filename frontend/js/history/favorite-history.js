export function recordFavoriteOperation(history, { label, favoriteId, favorite, setFavorite, renderNavigation, reportError, initialState }) {
  const renderBestEffort = async (state) => { try { await renderNavigation(state); } catch (error) { reportError(error); } };
  const apply = async (desired) => renderBestEffort(await setFavorite(favoriteId, desired));
  history.record({ label, undo: () => apply(!favorite), redo: () => apply(favorite) });
  void renderBestEffort(initialState);
}
