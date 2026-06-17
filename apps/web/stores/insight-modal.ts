import { create } from "zustand";
import type { ProactiveInsight } from "@/lib/types";

interface InsightModalState {
  insight: ProactiveInsight | null;
  open: (insight: ProactiveInsight) => void;
  close: () => void;
}

export const useInsightModal = create<InsightModalState>((set) => ({
  insight: null,
  open: (insight) => set({ insight }),
  close: () => set({ insight: null }),
}));
