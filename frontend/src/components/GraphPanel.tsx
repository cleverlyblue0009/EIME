import React from "react";
import { motion } from "framer-motion";
import { Eye, Move, SlidersHorizontal, Maximize2, Minimize2 } from "lucide-react";

import { useDashboardStore } from "../store/useDashboardStore";
import LegendPill from "./LegendPill";

const GraphPanel: React.FC = () => {
  const graph = useDashboardStore((state) => state.graph);
  const timeline = useDashboardStore((state) => state.timeline);

  const [zoom, setZoom] = React.useState(1);
  const [pan, setPan] = React.useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = React.useState(false);
  const [dragStart, setDragStart] = React.useState<{ x: number; y: number } | null>(null);
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;

    try {
      if (!isFullscreen) {
        await containerRef.current.requestFullscreen?.();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen?.();
        setIsFullscreen(false);
      }
    } catch (err) {
      console.error("Fullscreen error:", err);
    }
  };

  React.useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);


  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];

  // Keep inner container width reasonable for initial visibility
  // Nodes will be positioned within a normalized 100x100 space



  const computeNodePosition = (node: { id: string; type: string }, index: number) => {
    // Return percentages within the 0-100 viewBox
    if (node.type === "intended") {
      return { x: 10 + index * 12, y: 25 };
    }
    if (node.type === "actual") {
      const actualIndex = index - nodes.filter((n) => n.type === "intended").length;
      return { x: 50 + actualIndex * 12, y: 25 };
    }
    if (node.type === "divergence") {
      return { x: 30, y: 70 };
    }
    return { x: 50, y: 50 };
  };

  const clampZoom = (value: number) => Math.min(2.5, Math.max(0.7, value));

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (e.ctrlKey) {
      // Don't preventDefault on passive listeners; just handle zoom
      setZoom((prev) => clampZoom(prev - e.deltaY * 0.00125));
      return;
    }

    // regular scroll moves panel horizontally for better overview
    const target = e.currentTarget;
    target.scrollLeft += e.deltaY;
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !dragStart) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    setDragStart(null);
  };

  const zoomIn = () => setZoom((prev) => clampZoom(prev + 0.1));
  const zoomOut = () => setZoom((prev) => clampZoom(prev - 0.1));

  const resolvedPositions = Object.fromEntries(
    nodes.map((node, idx) => [
      node.id,
      computeNodePosition(node, idx),
    ])
  );

  const getColor = (type: string) => {
    switch (type) {
      case "intended":
        return "from-emerald-500 to-emerald-400 text-emerald-50 border-emerald-300/40";
      case "actual":
        return "from-blue-500 to-blue-400 text-blue-50 border-blue-300/40";
      case "divergence":
        return "from-red-500 to-rose-500 text-red-50 border-red-300/40";
      default:
        return "from-slate-500 to-slate-400 text-white border-white/10";
    }
  };

  return (
    <div
      ref={containerRef}
      className={`flex flex-col rounded-3xl border border-white/10 bg-slate-950/80 p-4 shadow-panel-2xl transition-all duration-300 ${
        isFullscreen
          ? "fixed inset-0 z-[9999] m-0 rounded-none border-none bg-slate-950 text-white overflow-hidden"
          : ""
      }`}
      style={isFullscreen ? { minHeight: "100vh", minWidth: "100vw" } : undefined}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-400">Intent · Execution Graph</p>
          <h2 className="text-3xl font-bold tracking-tight text-white">Visual Dual Execution</h2>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <button className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 transition hover:border-white hover:bg-white/10"><Eye size={14} /> Zoom</button>
          <button className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 transition hover:border-white hover:bg-white/10"><Move size={14} /> Pan</button>
          <button
            onClick={toggleFullscreen}
            className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 transition hover:border-white hover:bg-white/10"
            title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex gap-2">
            <LegendPill label="Intended" color="bg-emerald-500/15 text-emerald-300 border border-emerald-300/40" />
            <LegendPill label="Actual" color="bg-blue-500/15 text-blue-300 border border-blue-300/40" />
            <LegendPill label="Divergence" color="bg-red-500/15 text-red-300 border border-red-300/40" />
          </div>
          <div className="flex items-center gap-2">
            <button onClick={zoomOut} className="rounded-full border border-white/10 bg-slate-800/80 px-3 py-1 text-xs text-white hover:border-white">-</button>
            <span className="text-xs font-semibold text-white">Zoom {Math.round(zoom * 100)}%</span>
            <button onClick={zoomIn} className="rounded-full border border-white/10 bg-slate-800/80 px-3 py-1 text-xs text-white hover:border-white">+</button>
            <span className="text-xs text-slate-400">(Ctrl + wheel)</span>
          </div>
        </div>

        <div
          className={`relative w-full overflow-x-auto overflow-y-auto rounded-2xl border border-white/5 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-800/90 shadow-inner transition-all duration-300 ${
            isFullscreen ? "h-full" : "h-[480px]"
          }`}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{ cursor: isDragging ? "grabbing" : "grab" }}
        >
          <div
            className="relative h-full w-full"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: "top left",
              transition: isDragging ? "none" : "transform 0.12s ease-out",
            }}
          >
            {nodes.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                No graph data yet. Start analysis to visualize the execution chain.
              </div>
            ) : (
              <>
                <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ overflow: "visible", pointerEvents: "none" }}>
                  {edges.map((edge, idx) => {
                    const source = resolvedPositions[edge.source];
                    const target = resolvedPositions[edge.target];
                    if (!source || !target) return null;

                    const path = `M ${source.x} ${source.y} C ${source.x + 15} ${source.y} ${target.x - 15} ${target.y} ${target.x} ${target.y}`;
                    const stroke = edge.type === "divergence" ? "#fb7185" : edge.type === "intended" ? "#34d399" : "#60a5fa";

                    return (
                      <path
                        key={`${edge.id || edge.source}-${edge.target}-${idx}`}
                        d={path}
                        fill="none"
                        stroke={stroke}
                        strokeWidth={0.8}
                        opacity={0.9}
                        markerEnd="url(#arrow)"
                      />
                    );
                  })}

                  <defs>
                    <marker id="arrow" markerWidth="6" markerHeight="5" refX="6" refY="2.5" orient="auto" markerUnits="strokeWidth">
                      <path d="M0,0 L6,2.5 L0,5 Z" fill="#ffffff" />
                    </marker>
                  </defs>
                </svg>

                {nodes.map((node) => {
                  const position = resolvedPositions[node.id] || { x: 50, y: 50 };
                  const bg = getColor(node.type);
                  const isDivergence = node.type === "divergence";

                  return (
                    <motion.div
                      key={node.id}
                      initial={{ opacity: 0, scale: 0.85 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.35, delay: 0.04 }}
                      style={{ left: `${position.x}%`, top: `${position.y}%`, transform: "translate(-50%, -50%)" }}
                      className={`absolute z-10 max-w-[13rem] rounded-2xl border px-4 py-3 text-left shadow-lg ring-1 ring-white/10 backdrop-blur-sm ${isDivergence ? "border-red-300/70" : "border-white/10"} bg-gradient-to-br ${bg}`}
                    >
                      <p className="text-[10px] font-semibold uppercase tracking-widest text-white/70">{node.type}</p>
                      <p className="mt-1 text-sm font-bold text-white">{node.label || node.id}</p>
                      {node.id === graph.first_divergence && (
                        <span className="mt-2 inline-flex rounded-full bg-red-500/20 px-2 py-0.5 text-[11px] text-red-100">First divergence</span>
                      )}
                    </motion.div>
                  );
                })}
              </>
            )}
          </div>
        </div>
      </div>

      <div className={`mt-4 flex items-center justify-between rounded-2xl border border-white/5 bg-slate-900/60 px-4 py-3 transition-all duration-300 ${isFullscreen ? "hidden" : ""}`}>
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Timeline</p>
          <p className="text-sm text-white">t = {timeline.latency} · Frame {timeline.frame}</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <SlidersHorizontal size={16} />
          <div className="flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-[11px]">{timeline.progress}% loaded</div>
        </div>
      </div>
    </div>
  );
};

export default GraphPanel;
