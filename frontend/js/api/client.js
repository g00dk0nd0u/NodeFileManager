async function request(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
  return body;
}
export const getHealth = () => request("/api/health");
export const selectFolder = () => request("/api/folders/select", { method: "POST", body: "{}" });
export const getChildren = (id) => request(`/api/folders/children?id=${encodeURIComponent(id)}`);
export const openFile = (id) => request("/api/files/open", { method: "POST", body: JSON.stringify({ id }) });
export const renameItem = (id, name) => request("/api/items/rename", { method: "PATCH", body: JSON.stringify({ id, name }) });
export const copyItem = (id, destinationId) => request("/api/items/copy", { method: "POST", body: JSON.stringify({ id, destinationId }) });
export const moveItem = (id, destinationId) => request("/api/items/move", { method: "POST", body: JSON.stringify({ id, destinationId }) });
export const loadWorkspace = () => request("/api/workspace");
export const saveWorkspace = (state) => request("/api/workspace", { method: "PUT", body: JSON.stringify(state) });
