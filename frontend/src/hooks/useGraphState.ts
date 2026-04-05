import { create } from "zustand";

type GraphState = {
  graphMode: "hybrid" | "execution" | "intent" | "dataflow";
  showIntent: boolean;
  showData: boolean;
  showOnlyDivergence: boolean;
  detailLevel: "function" | "loop" | "step";
  setGraphMode: (graphMode: "hybrid" | "execution" | "intent" | "dataflow") => void;
  toggleIntent: () => void;
  toggleData: () => void;
  toggleDivergence: () => void;
  setDetailLevel: (detailLevel: "function" | "loop" | "step") => void;
};

const useGraphState = create<GraphState>((set) => ({
  graphMode: "hybrid",
  showIntent: true,
  showData: true,
  showOnlyDivergence: false,
  detailLevel: "step",
  setGraphMode: (graphMode) => set({ graphMode }),
  toggleIntent: () => set((state) => ({ showIntent: !state.showIntent })),
  toggleData: () => set((state) => ({ showData: !state.showData })),
  toggleDivergence: () =>
    set((state) => ({ showOnlyDivergence: !state.showOnlyDivergence })),
  setDetailLevel: (detailLevel) => set({ detailLevel }),
}));

export default useGraphState;
