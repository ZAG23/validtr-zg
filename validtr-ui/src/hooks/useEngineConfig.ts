import { useEffect } from "react";
import { getConfig } from "@/api/client";
import { useStore } from "@/store";

export function useEngineConfig() {
  const engineOnline = useStore((s) => s.engineOnline);
  const engineConfig = useStore((s) => s.engineConfig);
  const setEngineConfig = useStore((s) => s.setEngineConfig);

  useEffect(() => {
    if (!engineOnline || engineConfig) return;

    let mounted = true;

    async function fetch() {
      try {
        const config = await getConfig();
        if (mounted) setEngineConfig(config);
      } catch {
        // silently ignore — config is optional
      }
    }

    void fetch();

    return () => {
      mounted = false;
    };
  }, [engineOnline, engineConfig, setEngineConfig]);
}
