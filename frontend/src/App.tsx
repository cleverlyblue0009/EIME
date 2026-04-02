import React from "react";

import ControlsPanel from "./components/ControlsPanel";
import EditorPanel from "./components/EditorPanel";
import GraphPanel from "./components/GraphPanel";
import ReasoningPanel from "./components/ReasoningPanel";
import TimelineScrubber from "./components/TimelineScrubber";
import TopBar from "./components/TopBar";

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-brand-dark text-slate-100">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-6">
        <TopBar />

        <div className="grid gap-4 lg:grid-cols-[1.1fr_1.9fr_1fr]">
          <EditorPanel />

          <div className="order-last col-span-1 lg:order-none">
            <GraphPanel />
          </div>

          <ReasoningPanel />
        </div>

        <ControlsPanel />
        <TimelineScrubber />
      </div>
    </div>
  );
};

export default App;
