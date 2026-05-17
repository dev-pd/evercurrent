/* Persisted impersonation store. Holds the currently-selected user id and
   the currently-selected project id. localStorage-backed so reloads keep
   the selection. */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ImpersonationState {
  currentUserId: string | null;
  currentProjectId: string | null;
  currentDay: number;
  setCurrentUserId: (id: string | null) => void;
  setCurrentProjectId: (id: string | null) => void;
  setCurrentDay: (day: number) => void;
}

export const useImpersonationStore = create<ImpersonationState>()(
  persist(
    (set) => ({
      currentUserId: null,
      currentProjectId: null,
      currentDay: 1,
      setCurrentUserId: (id) => set({ currentUserId: id }),
      setCurrentProjectId: (id) => set({ currentProjectId: id }),
      setCurrentDay: (day) => set({ currentDay: day }),
    }),
    { name: "evercurrent-impersonation" },
  ),
);
