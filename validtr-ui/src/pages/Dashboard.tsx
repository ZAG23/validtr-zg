import { useStore } from "@/store";
import { RunForm } from "@/components/RunForm";
import { RunResultCard } from "@/components/RunResultCard";
import { RecentRunsList } from "@/components/RecentRunsList";
import { RunningIndicator } from "@/components/RunningIndicator";
import { EmptyState } from "@/components/EmptyState";

export function Dashboard() {
  const activeRun = useStore((s) => s.activeRun);
  const activeTask = useStore((s) => s.activeTask);
  const isRunning = useStore((s) => s.isRunning);
  const runs = useStore((s) => s.runs);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Page header */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-text-primary">Dashboard</h2>
        <p className="text-sm text-text-muted mt-1">
          Validate agentic stacks end-to-end
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: form + result */}
        <div className="lg:col-span-2 space-y-6">
          <RunForm />

          {isRunning && <RunningIndicator />}

          {activeRun && !isRunning && (
            <RunResultCard result={activeRun} task={activeTask} />
          )}

          {!activeRun && !isRunning && runs.length === 0 && (
            <EmptyState
              title="No runs yet"
              description="Enter a task description above and hit Run Validation to get started. validtr will recommend the optimal stack, execute the task, and score the results."
            />
          )}
        </div>

        {/* Right: recent runs */}
        <div>
          <RecentRunsList />
        </div>
      </div>
    </div>
  );
}
