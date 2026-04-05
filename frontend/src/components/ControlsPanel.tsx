import React from "react";
import { useDashboardStore } from "../store/useDashboardStore";

const ControlsPanel: React.FC = () => {
  const { inputSize, branchBehavior, scenario, setInputSize, setBranchBehavior, setScenario, simulation } =
    useDashboardStore((state) => ({
      inputSize: state.inputSize,
      branchBehavior: state.branchBehavior,
      scenario: state.scenario,
      setInputSize: state.setInputSize,
      setBranchBehavior: state.setBranchBehavior,
      setScenario: state.setScenario,
      simulation: state.simulation,
    }));

  const branchOptions: Array<"deterministic" | "random"> = ["deterministic", "random"];
  const scenarioOptions = ["Base", "Edge", "Stress Test"];

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 shadow-panel-md">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">Interactive Simulation</p>
          <h3 className="text-lg font-semibold text-white">Adjust execution inline</h3>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.3em] text-slate-300">
          Node-driven
        </span>
      </div>

      <div className="mt-4 space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <p>Input Size</p>
            <p>{inputSize}</p>
          </div>
          <input
            type="range"
            value={inputSize}
            min={10}
            max={120}
            onChange={(event) => setInputSize(Number(event.target.value))}
            className="w-full accent-indigo-500"
          />
        </div>

        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Branch Behavior</p>
          <div className="flex gap-2">
            {branchOptions.map((option) => (
              <button
                key={option}
                onClick={() => setBranchBehavior(option)}
                className={`flex-1 rounded-2xl border px-4 py-2 text-sm font-semibold transition ${
                  branchBehavior === option
                    ? "border-indigo-500 bg-indigo-500/30 text-white"
                    : "border-white/10 text-slate-200 hover:border-white/30"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Scenario</p>
          <div className="flex flex-wrap gap-2">
            {scenarioOptions.map((option) => (
              <button
                key={option}
                onClick={() => setScenario(option)}
                className={`rounded-2xl px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] transition ${
                  scenario === option
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : "border border-white/10 text-white/70 hover:border-white/40"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-white/10 bg-slate-900/70 p-4 text-sm text-slate-200">
        <p className="text-[11px] uppercase tracking-[0.4em] text-slate-500">Latest Simulation</p>
        <p className="mt-2 text-lg font-semibold text-white">{simulation.message}</p>
        <div className="mt-3 space-y-1 text-xs text-slate-400">
          {Object.entries(simulation.metrics).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between">
              <span className="capitalize">{key.replace("_", " ")}</span>
              <span className="font-semibold text-white">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ControlsPanel;
