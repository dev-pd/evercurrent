import { create } from "zustand";
import { ASYNC_JOB_TIMEOUT_MS } from "@/lib/constants";

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
    safety = setTimeout(() => set({ pending: false }), ASYNC_JOB_TIMEOUT_MS);
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
