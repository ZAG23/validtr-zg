import type { AttemptInfo } from "@/api/types";
import { cn, formatScore, scoreColor } from "@/lib/utils";

export function AttemptTimeline({
  attempts,
  bestAttempt,
}: {
  attempts: AttemptInfo[];
  bestAttempt: number;
}) {
  if (attempts.length <= 1) return null;

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
        Attempts
      </h4>
      <div className="space-y-0">
        {attempts.map((a, i) => {
          const isBest = a.attempt_number === bestAttempt;
          return (
            <div key={a.attempt_number} className="flex items-start gap-3">
              {/* Timeline line + dot */}
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "w-2.5 h-2.5 rounded-full border-2 shrink-0",
                    isBest
                      ? "bg-accent border-accent"
                      : "bg-surface-2 border-border-bright",
                  )}
                />
                {i < attempts.length - 1 && (
                  <div className="w-px h-8 bg-border" />
                )}
              </div>

              {/* Content */}
              <div className="pb-4">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-text-primary">
                    #{a.attempt_number}
                  </span>
                  <span className={cn("font-mono text-sm", scoreColor(a.score))}>
                    {formatScore(a.score)}
                  </span>
                  {isBest && (
                    <span className="text-[10px] text-accent font-semibold tracking-wider">
                      BEST
                    </span>
                  )}
                </div>
                <div className="text-xs text-text-muted mt-0.5">
                  {a.stack.provider} / {a.stack.model}
                </div>
                {a.adjustment_notes.map((note, j) => (
                  <p
                    key={j}
                    className="text-xs text-text-secondary mt-1 pl-2 border-l border-warn/40"
                  >
                    {note}
                  </p>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
