import { useStore } from "@/store";
import { cn, formatScore, scoreColor, truncate, relativeTime } from "@/lib/utils";

export function RecentRunsList() {
  const runs = useStore((s) => s.runs);
  const setActiveRun = useStore((s) => s.setActiveRun);
  const activeRun = useStore((s) => s.activeRun);

  if (runs.length === 0) return null;

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
        Recent Runs
      </h4>
      <div className="space-y-1">
        {runs.map((run) => {
          const isActive = activeRun?.run_id === run.run_id;
          return (
            <button
              key={run.run_id + run.timestamp}
              onClick={() => setActiveRun(run, run.task)}
              className={cn(
                "w-full text-left p-3 rounded-lg border transition-colors",
                isActive
                  ? "bg-surface-2 border-accent/30"
                  : "bg-surface-1 border-border hover:border-border-bright",
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-text-muted">
                  #{run.run_id}
                </span>
                <span className={cn("font-mono text-sm font-semibold", scoreColor(run.score))}>
                  {formatScore(run.score)}
                </span>
              </div>
              <p className="text-sm text-text-primary leading-snug mb-1">
                {truncate(run.task, 80)}
              </p>
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-text-muted">
                  {run.provider}
                </span>
                <span className="text-xs text-text-muted">
                  {relativeTime(run.timestamp)}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
