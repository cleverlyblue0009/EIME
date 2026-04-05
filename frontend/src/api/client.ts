const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export const simulate = async (patch: unknown) => {
  const response = await fetch(`${API_BASE}/simulate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(patch),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Simulation failed: ${errorText}`);
  }

  return response.json();
};
