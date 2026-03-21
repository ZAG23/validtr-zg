import type { RunResponse } from "@/api/types";
import { ScoreGauge } from "./ScoreGauge";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { StackCard } from "./StackCard";
import { AttemptTimeline } from "./AttemptTimeline";

export function RunResultCard({
  result,
  task,
}: {
  result: RunResponse;
  task?: string | null;
}) {
  return (
    <div className="bg-surface-1 border border-border rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h3 className="font-mono text-sm text-text-secondary">
            Run #{result.run_id}
          </h3>
          {task && (
            <p className="text-sm text-text-primary max-w-lg">{task}</p>
          )}
        </div>
        <div className="text-right text-xs text-text-muted font-mono space-y-0.5">
          <div>{result.total_attempts} attempt{result.total_attempts !== 1 ? "s" : ""}</div>
          <div>{result.artifact_count} artifact{result.artifact_count !== 1 ? "s" : ""}</div>
        </div>
      </div>

      {/* Score gauge + breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
        <div className="flex justify-center">
          <ScoreGauge score={result.score} />
        </div>
        <ScoreBreakdown dimensions={result.dimensions} />
      </div>

      {/* Divider */}
      <div className="border-t border-border" />

      {/* Stack info */}
      <StackCard stack={result.stack} />

      {/* Attempt timeline */}
      {result.attempts.length > 1 && (
        <>
          <div className="border-t border-border" />
          <AttemptTimeline
            attempts={result.attempts}
            bestAttempt={result.best_attempt}
          />
        </>
      )}

      {/* Artifacts preview */}
      {result.artifact_count > 0 && (
        <>
          <div className="border-t border-border" />
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Artifacts
            </h4>
            <div className="flex flex-wrap gap-2">
              {Object.keys(result.artifacts).map((name) => (
                <span
                  key={name}
                  className="inline-flex items-center px-2 py-1 rounded border border-border-bright bg-surface-2 font-mono text-xs text-text-secondary"
                >
                  {name}
                </span>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
