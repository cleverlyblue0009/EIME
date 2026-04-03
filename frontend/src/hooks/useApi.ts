const API_BASE = "http://localhost:8000/api";

type AnalyzePayload = {
  code: string; // make required (backend needs it)
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
        language: "python", // backend expects this (default but safe)
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
};

export async function simulateScenario(payload: SimulationPayload) {
  try {
    const response = await fetch(`${API_BASE}/simulate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        code: payload.code,
        input_size: payload.input_size ?? 10,
        branch_mode: payload.branch_mode ?? "deterministic",
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