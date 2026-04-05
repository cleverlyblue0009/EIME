import CodeEditor from "./components/CodeEditor";
import GraphViewer from "./components/GraphViewer";
import NodeInspector from "./components/NodeInspector";
import ReasoningPanel from "./components/ReasoningPanel";
import MetricsBar from "./components/MetricsBar";
import TraceTimeline from "./components/TraceTimeline";
import SimulationControls from "./components/SimulationControls";

const App = () => {
  return (
    <div className="app-shell">
      <header className="panel">
        <div className="panel-header">
          <div>
            <h1 style={{ margin: 0, fontSize: 22 }}>IME Universal</h1>
            <p style={{ margin: 0, color: "var(--text-secondary)" }}>
              Intent Modeling Engine — LeetCode-grade reasoning and divergence detection
            </p>
          </div>
        </div>
      </header>

      <MetricsBar />

      <div className="ime-grid">
        <div className="panel">
          <CodeEditor />
        </div>

        <div className="panel graph-surface">
          <GraphViewer />
        </div>

        <div className="panel">
          <ReasoningPanel />
          <NodeInspector />
          <SimulationControls />
        </div>
      </div>

      <TraceTimeline />
    </div>
  );
};

export default App;
