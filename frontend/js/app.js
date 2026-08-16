import { getHealth } from "./api/client.js";

const status = document.querySelector("#backend-status");

try {
  const health = await getHealth();
  status.textContent = health.status === "ok"
    ? "バックエンド接続: 正常"
    : "バックエンド接続: 不明な応答";
} catch (error) {
  console.error("Health check failed", error);
  status.textContent = "バックエンド接続: 失敗";
}
