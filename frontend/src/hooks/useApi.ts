const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

type AnalyzePayload = {
  code: string;
  gemini_api_key?: string | null;
};

export async function analyzeCode(payload: AnalyzePayload) {
  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        code: payload.code,
        gemini_api_key: payload.gemini_api_key || null,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Analyze failed: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Analyze error:", error);
    throw error;
  }
}

type SimulationPayload = {
  code: string;
  input_size?: number;
  branch_mode?: "deterministic" | "random";
  overrides?: Record<string, unknown>;
};

export async function simulateScenario(payload: SimulationPayload) {
  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        code: payload.code,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Simulation failed: ${errorText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Simulation error:", error);
    throw error;
  }
}
