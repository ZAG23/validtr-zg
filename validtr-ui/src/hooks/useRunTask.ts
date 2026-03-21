import { useCallback, useRef } from "react";
import { runTask } from "@/api/client";
import { useStore } from "@/store";
import type { RunRequest, StoredRun } from "@/api/types";

export function useRunTask() {
  const {
    isRunning,
    runError,
    setActiveRun,
    setIsRunning,
    setRunError,
    setRunStartTime,
    addRun,
  } = useStore();

  const abortRef = useRef<AbortController | null>(null);

  const execute = useCallback(
    async (req: RunRequest) => {
      if (isRunning) return;

      abortRef.current = new AbortController();
      setIsRunning(true);
      setRunError(null);
      setActiveRun(null, req.task);
      setRunStartTime(Date.now());

      try {
        const result = await runTask(req, abortRef.current.signal);
        setActiveRun(result, req.task);

        const stored: StoredRun = {
          ...result,
          task: req.task,
          provider: req.provider,
          timestamp: Date.now(),
        };
        addRun(stored);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          setRunError("Run cancelled");
        } else if (err instanceof Error) {
          setRunError(err.message);
        } else {
          setRunError("An unexpected error occurred");
        }
      } finally {
        setIsRunning(false);
        setRunStartTime(null);
        abortRef.current = null;
      }
    },
    [isRunning, setActiveRun, setIsRunning, setRunError, setRunStartTime, addRun],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { execute, cancel, isRunning, error: runError };
}
