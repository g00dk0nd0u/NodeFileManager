async function request(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
  return body;
}
export const getHealth = () => request("/api/health");
export const selectFolder = () => request("/api/folders/select", { method: "POST", body: "{}" });
export const getChildren = (id) => request(`/api/folders/children?id=${encodeURIComponent(id)}`);
export const loadWorkspace = () => request("/api/workspace");
export const saveWorkspace = (state) => request("/api/workspace", { method: "PUT", body: JSON.stringify(state) });
