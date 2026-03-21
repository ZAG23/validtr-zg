import { NavLink } from "react-router";
import { useStore } from "@/store";
import { cn } from "@/lib/utils";

const NAV_ITEMS: readonly { to: string; label: string; disabled?: boolean }[] = [
  { to: "/", label: "Dashboard" },
  { to: "/runs", label: "Runs", disabled: true },
  { to: "/mcp", label: "MCP Explorer", disabled: true },
];

export function Sidebar() {
  const engineOnline = useStore((s) => s.engineOnline);

  return (
    <aside className="w-60 h-screen bg-surface-1 border-r border-border flex flex-col shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <h1 className="font-mono text-xl font-bold text-accent tracking-tight">
          validtr
        </h1>
        <p className="font-mono text-[10px] text-text-muted mt-0.5">
          agentic stack validation
        </p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) =>
          item.disabled ? (
            <div
              key={item.to}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-text-muted cursor-not-allowed"
            >
              {item.label}
              <span className="ml-auto text-[10px] text-text-muted/50">soon</span>
            </div>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                  isActive
                    ? "bg-surface-2 text-accent"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface-2",
                )
              }
            >
              {item.label}
            </NavLink>
          ),
        )}
      </nav>

      {/* Engine status */}
      <div className="px-5 py-4 border-t border-border">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-2 h-2 rounded-full",
              engineOnline ? "bg-pass" : "bg-fail",
            )}
          />
          <span className="text-xs text-text-muted">
            Engine {engineOnline ? "online" : "offline"}
          </span>
        </div>
      </div>
    </aside>
  );
}
