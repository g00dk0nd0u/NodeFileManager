export class HistoryManager {
  constructor({ limit = 100, onChange = () => {} } = {}) {
    this.limit = limit; this.onChange = onChange; this.undoStack = []; this.redoStack = []; this.busy = false; this.replaying = false;
  }
  get canUndo() { return this.undoStack.length > 0 && !this.busy; }
  get canRedo() { return this.redoStack.length > 0 && !this.busy; }
  record(entry) { this.#validate(entry); if (this.replaying || this.busy) return false; this.#append(entry); this.#changed(); return true; }
  async execute(entry) { this.#validate(entry); if (this.busy) return false; this.busy = true; this.#changed(); try { await entry.redo(); this.#append(entry); return true; } finally { this.busy = false; this.#changed(); } }
  async undo() { return this.#replay(this.undoStack, this.redoStack, "undo"); }
  async redo() { return this.#replay(this.redoStack, this.undoStack, "redo"); }
  async #replay(source, destination, method) { if (this.busy || !source.length) return false; const entry = source.at(-1); this.busy = true; this.replaying = true; this.#changed(); try { await entry[method](); source.pop(); destination.push(entry); return true; } finally { this.replaying = false; this.busy = false; this.#changed(); } }
  #append(entry) { this.undoStack.push(entry); if (this.undoStack.length > this.limit) this.undoStack.splice(0, this.undoStack.length - this.limit); this.redoStack.length = 0; }
  #validate(entry) { if (!entry || typeof entry.label !== "string" || !entry.label || typeof entry.undo !== "function" || typeof entry.redo !== "function") throw new TypeError("History entries require a label, undo(), and redo()"); }
  #changed() { this.onChange({ canUndo: this.canUndo, canRedo: this.canRedo, undoLabel: this.undoStack.at(-1)?.label, redoLabel: this.redoStack.at(-1)?.label }); }
}

export function isEditableTarget(target) {
  return Boolean(target?.closest?.("input, textarea, [contenteditable]:not([contenteditable='false'])"));
}

export function historyShortcut(event, platform = globalThis.navigator?.platform || "") {
  const mac = /Mac|iPhone|iPad|iPod/.test(platform);
  if ((mac ? !event.metaKey || event.ctrlKey : !event.ctrlKey || event.metaKey) || event.altKey || isEditableTarget(event.target)) return null;
  const key = event.key.toLowerCase();
  if (key === "z") return event.shiftKey ? "redo" : "undo";
  if (key === "y" && event.ctrlKey && !event.metaKey && !event.shiftKey) return "redo";
  return null;
}
