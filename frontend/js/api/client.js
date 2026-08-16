export async function getHealth() {
  const response = await fetch("/api/health", {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Health endpoint returned ${response.status}`);
  }

  return response.json();
}
