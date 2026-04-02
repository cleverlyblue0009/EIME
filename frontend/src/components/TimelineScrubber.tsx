import React from "react";
import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";

import { useDashboardStore } from "../store/useDashboardStore";

const TimelineScrubber: React.FC = () => {
  const timeline = useDashboardStore((state) => state.timeline);

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-4 shadow-panel-md">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Timeline Scrubber</p>
          <p className="text-sm text-white/80">Playback controls & zoom</p>
        </div>
        <div className="flex items-center gap-3 text-slate-400">
          <button className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-xs hover:border-white">
            <ChevronLeft size={16} />
          </button>
          <button className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-xs hover:border-white">
            <Play size={16} />
          </button>
          <button className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-xs hover:border-white">
            <Pause size={16} />
          </button>
          <button className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-xs hover:border-white">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={100}
          value={timeline.progress}
          readOnly
          className="h-1 w-full accent-emerald-500"
        />
        <span className="text-xs text-slate-400">Frame {timeline.frame}</span>
      </div>
    </div>
  );
};

export default TimelineScrubber;
