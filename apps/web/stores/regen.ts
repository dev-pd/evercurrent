import { create } from "zustand";

interface RegenState {
  pending: boolean;
  start: () => void;
  done: () => void;
}

let safety: ReturnType<typeof setTimeout> | null = null;

export const useRegen = create<RegenState>((set) => ({
  pending: false,
  start: () => {
    if (safety) clearTimeout(safety);
    safety = setTimeout(() => set({ pending: false }), 45_000);
    set({ pending: true });
  },
  done: () => {
    if (safety) {
      clearTimeout(safety);
      safety = null;
    }
    set({ pending: false });
  },
}));
