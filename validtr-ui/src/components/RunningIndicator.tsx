import { useStore } from "@/store";

export function RunningIndicator() {
  const isRunning = useStore((s) => s.isRunning);
  const activeTask = useStore((s) => s.activeTask);

  if (!isRunning) return null;

  return (
    <div className="bg-surface-1 border border-border rounded-lg p-6">
      <div className="flex items-center gap-4">
        {/* Pulsing dots animation */}
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
          <div className="w-2 h-2 rounded-full bg-accent animate-pulse [animation-delay:150ms]" />
          <div className="w-2 h-2 rounded-full bg-accent animate-pulse [animation-delay:300ms]" />
        </div>
        <div>
          <p className="text-sm text-text-primary">Running validation...</p>
          {activeTask && (
            <p className="text-xs text-text-muted mt-0.5 max-w-md truncate">
              {activeTask}
            </p>
          )}
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <div className="h-1 rounded-full bg-surface-3 overflow-hidden">
          <div className="h-full w-1/3 rounded-full bg-accent/50 animate-[shimmer_2s_ease-in-out_infinite]" />
        </div>
        <p className="text-xs text-text-muted font-mono">
          This may take a few minutes depending on task complexity
        </p>
      </div>
    </div>
  );
}
