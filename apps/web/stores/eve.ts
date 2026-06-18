import { create } from "zustand";
import { EVE_JOB_TIMEOUT_MS } from "@/lib/constants";

interface EveState {
  running: boolean;
  start: () => void;
  done: () => void;
}

// Module-level timer so the "investigating" state + its safety timeout survive
// page navigation (the button is per-page; this store is global, like useRegen).
let safety: ReturnType<typeof setTimeout> | null = null;

export const useEve = create<EveState>((set) => ({
  running: false,
  start: () => {
    if (safety) clearTimeout(safety);
    safety = setTimeout(() => set({ running: false }), EVE_JOB_TIMEOUT_MS);
    set({ running: true });
  },
  done: () => {
    if (safety) {
      clearTimeout(safety);
      safety = null;
    }
    set({ running: false });
  },
}));
