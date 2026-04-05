import React from "react";
import Editor from "@monaco-editor/react";

import { useDashboardStore } from "../store/useDashboardStore";
import { useDebouncedEffect } from "../hooks/useDebouncedEffect";

const EditorPanel: React.FC = () => {
  const code = useDashboardStore((state) => state.code);
  const setCode = useDashboardStore((state) => state.setCode);
  const analyze = useDashboardStore((state) => state.analyze);

  useDebouncedEffect(
    () => {
      if (code.trim().length > 0) {
        void analyze(code);
      }
    },
    [code],
    300
  );

  return (
    <div className="flex flex-col rounded-3xl border border-white/5 bg-slate-900/80 shadow-panel-md">
      <div className="flex items-center justify-between px-4 py-3 text-xs uppercase tracking-[0.4em] text-slate-400">
        CODE EDITOR
        <span className="rounded-full border border-slate-600 px-3 py-1 text-[11px] font-semibold text-slate-200">Python 3.11</span>
      </div>
      <div className="h-[520px]">
        <Editor
          defaultLanguage="python"
          defaultValue={code}
          value={code}
          onChange={(value) => {
            if (value !== undefined) {
              setCode(value);
            }
          }}
          options={{
            fontSize: 13,
            minimap: { enabled: false },
            automaticLayout: true,
            theme: "vs-dark",
            scrollBeyondLastLine: false,
          }}
        />
      </div>
    </div>
  );
};

export default EditorPanel;
