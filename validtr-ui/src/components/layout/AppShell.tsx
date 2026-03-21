import { Outlet } from "react-router";
import { Sidebar } from "./Sidebar";
import { useHealthCheck } from "@/hooks/useHealthCheck";
import { useEngineConfig } from "@/hooks/useEngineConfig";

export function AppShell() {
  useHealthCheck();
  useEngineConfig();

  return (
    <div className="flex h-screen bg-surface-0">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
