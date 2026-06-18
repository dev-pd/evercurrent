import { create } from "zustand";

interface DecisionModalState {
  signalId: string | null;
  open: (id: string) => void;
  close: () => void;
}

export const useDecisionModal = create<DecisionModalState>((set) => ({
  signalId: null,
  open: (id) => set({ signalId: id }),
  close: () => set({ signalId: null }),
}));
