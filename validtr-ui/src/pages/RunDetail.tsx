import { useParams } from "react-router";
import { useStore } from "@/store";
import { RunResultCard } from "@/components/RunResultCard";
import { EmptyState } from "@/components/EmptyState";

export function RunDetail() {
  const { runId } = useParams();
  const runs = useStore((s) => s.runs);
  const run = runs.find((r) => r.run_id === runId);

  if (!run) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <EmptyState
          title="Run not found"
          description={`No run with ID "${runId ?? ""}" found in history.`}
        />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-text-primary">Run Detail</h2>
      </div>
      <RunResultCard result={run} task={run.task} />
    </div>
  );
}
