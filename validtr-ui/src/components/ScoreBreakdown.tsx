import type { DimensionScore } from "@/api/types";

export function ScoreBreakdown({
  dimensions,
}: {
  dimensions: DimensionScore[];
}) {
  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
        Score Breakdown
      </h4>
      {dimensions.map((d) => {
        const pct = d.max_score > 0 ? (d.score / d.max_score) * 100 : 0;
        return (
          <div key={d.name} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-text-secondary">{d.name}</span>
              <span className="font-mono text-text-primary">
                {d.score}/{d.max_score}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{
                  width: `${pct}%`,
                  backgroundColor:
                    pct >= 90
                      ? "var(--color-pass)"
                      : pct >= 70
                        ? "var(--color-warn)"
                        : "var(--color-fail)",
                }}
              />
            </div>
            {d.details && (
              <p className="text-xs text-text-muted">{d.details}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
