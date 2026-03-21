import { useEffect } from "react";
import { getHealth } from "@/api/client";
import { useStore } from "@/store";

export function useHealthCheck(intervalMs = 10_000) {
  const setEngineOnline = useStore((s) => s.setEngineOnline);

  useEffect(() => {
    let mounted = true;

    async function check() {
      try {
        await getHealth();
        if (mounted) setEngineOnline(true);
      } catch {
        if (mounted) setEngineOnline(false);
      }
    }

    void check();
    const id = setInterval(() => void check(), intervalMs);

    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [intervalMs, setEngineOnline]);
}
