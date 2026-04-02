from datetime import datetime
from random import uniform
from typing import Dict


def run_simulation(scenario: str, input_size: int, branch_behavior: str) -> Dict:
    severity = "LOW" if input_size <= 30 else "MEDIUM"
    if branch_behavior.lower() == "chaotic":
        severity = "HIGH"

    return {
        "scenario": scenario or "base",
        "status": "ready",
        "message": (
            f"Simulation completed for {scenario or 'base'} scenario with "
            f"{input_size} inputs and {branch_behavior} branching."
        ),
        "metrics": {
            "started_at": datetime.utcnow().isoformat() + "Z",
            "divergence_risk": f"{uniform(0.1, 0.4):.2f}",
            "severity": severity,
        },
    }
