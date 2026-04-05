import { useEffect, useState } from "react";

import useIMEAnalysis from "../hooks/useIMEAnalysis";

const PLAY_INTERVAL_MS = 900;

const TraceTimeline = () => {
  const { analysisResult, selectNode, selectedNodeId } = useIMEAnalysis();
  const steps = analysisResult?.normalized_trace?.steps ?? [];
  const [isPlaying, setIsPlaying] = useState(false);
  const [playIndex, setPlayIndex] = useState(0);

  useEffect(() => {
    if (!isPlaying || steps.length === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      setPlayIndex((current) => {
        const next = current + 1;
        if (next >= steps.length) {
          setIsPlaying(false);
          return current;
        }
        const nextStep = steps[next];
        selectNode(`step_${nextStep.step_id}`);
        return next;
      });
    }, PLAY_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [isPlaying, steps, selectNode]);

  useEffect(() => {
    if (!steps.length) {
      setIsPlaying(false);
      setPlayIndex(0);
      return;
    }
    const selectedIndex = steps.findIndex((step: any) => `step_${step.step_id}` === selectedNodeId);
    if (selectedIndex >= 0) {
      setPlayIndex(selectedIndex);
    }
  }, [steps, selectedNodeId]);

  if (!steps.length) {
    return null;
  }

  return (
    <div className="trace-timeline">
      <button className="button-secondary" onClick={() => {
        if (!isPlaying && steps.length > 0 && !selectedNodeId) {
          selectNode(`step_${steps[0].step_id}`);
          setPlayIndex(0);
        }
        setIsPlaying((value) => !value);
      }}>
        {isPlaying ? "Pause" : "Play"}
      </button>
      {steps.map((step: any) => (
        <div
          key={step.step_id}
          className={`trace-pill ${selectedNodeId === `step_${step.step_id}` ? "active" : ""}`}
          onClick={() => {
            setIsPlaying(false);
            setPlayIndex(steps.findIndex((candidate: any) => candidate.step_id === step.step_id));
            selectNode(`step_${step.step_id}`);
          }}
        >
          {step.step_id}: {step.description}
        </div>
      ))}
    </div>
  );
};

export default TraceTimeline;
