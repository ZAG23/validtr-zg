import type { StackInfo } from "@/api/types";

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded border border-border-bright bg-surface-2 font-mono text-xs text-text-secondary">
      {children}
    </span>
  );
}

export function StackCard({ stack }: { stack: StackInfo }) {
  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
        Recommended Stack
      </h4>

      <div className="space-y-2">
        {/* Provider + Model */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted w-16 shrink-0">LLM</span>
          <span className="font-mono text-sm text-accent">
            {stack.provider} / {stack.model}
          </span>
        </div>

        {/* Framework — only show when one was recommended */}
        {stack.framework && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted w-16 shrink-0">
              Framework
            </span>
            <span className="font-mono text-sm text-text-secondary">
              {stack.framework}
            </span>
          </div>
        )}

        {/* MCP Servers */}
        {stack.mcp_servers.length > 0 && (
          <div className="flex items-start gap-2">
            <span className="text-xs text-text-muted w-16 shrink-0 pt-0.5">
              MCP
            </span>
            <div className="flex flex-wrap gap-1">
              {stack.mcp_servers.map((s) => (
                <Tag key={s}>{s}</Tag>
              ))}
            </div>
          </div>
        )}

        {/* Skills */}
        {stack.skills.length > 0 && (
          <div className="flex items-start gap-2">
            <span className="text-xs text-text-muted w-16 shrink-0 pt-0.5">
              Skills
            </span>
            <div className="flex flex-wrap gap-1">
              {stack.skills.map((s) => (
                <Tag key={s}>{s}</Tag>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Adjustment Notes */}
      {stack.adjustment_notes.length > 0 && (
        <div className="mt-2 space-y-1">
          <span className="text-xs text-text-muted">Adjustments</span>
          {stack.adjustment_notes.map((note, i) => (
            <p key={i} className="text-xs text-text-secondary pl-3 border-l border-warn/40">
              {note}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
