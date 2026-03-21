import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { RunResponse, StoredRun, EngineConfig } from "@/api/types";

const MAX_STORED_RUNS = 50;

interface ValidtrStore {
  // Persisted: recent runs
  runs: StoredRun[];
  addRun: (run: StoredRun) => void;
  removeRun: (runId: string) => void;
  clearRuns: () => void;

  // Transient: active run
  activeRun: RunResponse | null;
  activeTask: string | null;
  isRunning: boolean;
  runError: string | null;
  runStartTime: number | null;
  setActiveRun: (run: RunResponse | null, task?: string) => void;
  setIsRunning: (v: boolean) => void;
  setRunError: (err: string | null) => void;
  setRunStartTime: (t: number | null) => void;

  // Engine
  engineOnline: boolean;
  setEngineOnline: (v: boolean) => void;
  engineConfig: EngineConfig | null;
  setEngineConfig: (c: EngineConfig) => void;
}

export const useStore = create<ValidtrStore>()(
  persist(
    (set) => ({
      // Persisted
      runs: [],
      addRun: (run) =>
        set((state) => ({
          runs: [run, ...state.runs].slice(0, MAX_STORED_RUNS),
        })),
      removeRun: (runId) =>
        set((state) => ({
          runs: state.runs.filter((r) => r.run_id !== runId),
        })),
      clearRuns: () => set({ runs: [] }),

      // Transient
      activeRun: null,
      activeTask: null,
      isRunning: false,
      runError: null,
      runStartTime: null,
      setActiveRun: (run, task) =>
        set({ activeRun: run, activeTask: task ?? null }),
      setIsRunning: (v) => set({ isRunning: v }),
      setRunError: (err) => set({ runError: err }),
      setRunStartTime: (t) => set({ runStartTime: t }),

      // Engine
      engineOnline: false,
      setEngineOnline: (v) => set({ engineOnline: v }),
      engineConfig: null,
      setEngineConfig: (c) => set({ engineConfig: c }),
    }),
    {
      name: "validtr-runs",
      partialize: (state) => ({ runs: state.runs }),
    },
  ),
);
