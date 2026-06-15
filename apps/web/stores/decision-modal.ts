import { create } from "zustand";

interface DecisionModalState {
  cardId: string | null;
  open: (id: string) => void;
  close: () => void;
}

export const useDecisionModal = create<DecisionModalState>((set) => ({
  cardId: null,
  open: (id) => set({ cardId: id }),
  close: () => set({ cardId: null }),
}));
