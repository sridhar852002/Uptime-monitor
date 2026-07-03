const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchUrls() {
  const response = await fetch(`${API_BASE}/urls`);
  if (!response.ok) {
    throw new Error("Failed to load monitored URLs");
  }
  return response.json();
}

export async function addUrl(url) {
  const response = await fetch(`${API_BASE}/urls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = error.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || String(item)).join(", ")
          : "Failed to add URL";
    throw new Error(message);
  }

  return response.json();
}

export async function deleteUrl(id) {
  const response = await fetch(`${API_BASE}/urls/${id}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("Failed to delete URL");
  }
}
