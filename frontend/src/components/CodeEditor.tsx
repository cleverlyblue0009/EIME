import { useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";

import useIMEAnalysis from "../hooks/useIMEAnalysis";

const CodeEditor = () => {
  const {
    code,
    setCode,
    geminiApiKey,
    setGeminiApiKey,
    analyze,
    isAnalyzing,
    analysisStage,
    analysisResult,
    analysisError,
  } = useIMEAnalysis();
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationRef = useRef<string[]>([]);

  useEffect(() => {
    if (!editorRef.current || !monacoRef.current) {
      return;
    }
    const monaco = monacoRef.current;
    const editor = editorRef.current;
    const divergences = analysisResult?.divergences ?? [];
    const newDecorations = divergences.map((div: any) => ({
      range: new monaco.Range(div.first_occurrence_line, 1, div.first_occurrence_line, 1),
      options: {
        isWholeLine: true,
        className: "line-divergence",
        glyphMarginClassName: "line-divergence-glyph",
        hoverMessage: { value: `[Divergence] ${div.type}: ${div.actual_behavior}` },
      },
    }));
    decorationRef.current = editor.deltaDecorations(
      decorationRef.current,
      newDecorations
    );
  }, [analysisResult]);

  return (
    <div>
      <div className="panel-header">
        <div>
          <h2 style={{ margin: 0 }}>Code</h2>
          <p style={{ margin: 0, color: "var(--text-secondary)" }}>
            Paste any Python program, function, or script. IME is designed to analyze arbitrary code, not just preset examples.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="button-primary" onClick={() => void analyze()} disabled={isAnalyzing}>
            {isAnalyzing ? "Analyzing..." : "Analyze"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>
          Mandatory Gemini reasoning runs after the deterministic trace and divergence pass. Leave the key blank to use
          the backend <code>.env</code>, or provide a request-specific override here.
        </p>
        <input
          value={geminiApiKey}
          onChange={(event) => setGeminiApiKey(event.target.value)}
          placeholder="Optional Gemini API key override"
        />
      </div>

      <div className="code-editor" style={{ position: "relative" }}>
        {!code.trim() ? (
          <div
            style={{
              position: "absolute",
              top: 16,
              left: 16,
              right: 16,
              zIndex: 2,
              color: "var(--text-secondary)",
              pointerEvents: "none",
              lineHeight: 1.6,
            }}
          >
            Paste any Python program here.
            <br />
            IME will run the deterministic engine first, then the mandatory Gemini reasoning pass to explain where behavior diverges.
          </div>
        ) : null}

        <Editor
          height="100%"
          defaultLanguage="python"
          value={code}
          onChange={(value) => setCode(value || "")}
          onMount={(editor, monaco) => {
            editorRef.current = editor;
            monacoRef.current = monaco;
          }}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "JetBrains Mono, Menlo, monospace",
            glyphMargin: true,
          }}
        />
      </div>

      {analysisError ? (
        <p style={{ marginTop: 8, color: "#fda4af" }}>{analysisError}</p>
      ) : (
        <p style={{ marginTop: 8, color: "var(--text-secondary)" }}>
          Status: {analysisStage || "idle"}
        </p>
      )}
    </div>
  );
};

export default CodeEditor;
