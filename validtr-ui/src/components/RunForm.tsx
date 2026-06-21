import { useState, useCallback, useEffect } from "react";
import { useRunTask } from "@/hooks/useRunTask";
import { useStore } from "@/store";
import { cn } from "@/lib/utils";
import type { RunRequest } from "@/api/types";

const PROVIDERS = ["anthropic", "openai", "gemini"];

const PROVIDER_ENV_VARS: Record<string, string> = {
  anthropic: "ANTHROPIC_API_KEY",
  openai: "OPENAI_API_KEY",
  gemini: "GOOGLE_API_KEY",
};

export function RunForm() {
  const { execute, cancel, isRunning, error } = useRunTask();
  const engineOnline = useStore((s) => s.engineOnline);
  const runStartTime = useStore((s) => s.runStartTime);

  const [task, setTask] = useState("");
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [model, setModel] = useState("");
  const [maxAttempts, setMaxAttempts] = useState(1);
  const [scoreThreshold, setScoreThreshold] = useState(95);
  const [timeout, setTimeout_] = useState(300);
  const [dryRun, setDryRun] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // Elapsed time counter
  useEffect(() => {
    if (!runStartTime) {
      setElapsed(0);
      return;
    }
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - runStartTime) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [runStartTime]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!task.trim() || isRunning) return;

      const req: RunRequest = {
        task: task.trim(),
        provider,
        dry_run: dryRun,
      };
      if (apiKey.trim()) req.api_key = apiKey.trim();
      if (model.trim()) req.model = model.trim();
      if (maxAttempts !== 1) req.max_attempts = maxAttempts;
      if (scoreThreshold !== 95) req.score_threshold = scoreThreshold;
      if (timeout !== 300) req.timeout = timeout;

      void execute(req);
    },
    [task, provider, apiKey, model, maxAttempts, scoreThreshold, timeout, dryRun, isRunning, execute],
  );

  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Task input */}
      <div>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Describe the task to validate..."
          rows={3}
          className="w-full bg-surface-1 border border-border rounded-lg px-4 py-3 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/25 resize-y"
        />
      </div>

      {/* API key + Provider row */}
      <div className="flex items-center gap-3">
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="bg-surface-1 border border-border rounded-lg px-3 py-2 font-mono text-sm text-text-primary focus:outline-none focus:border-accent/50"
        >
          {PROVIDERS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={`API key (or set ${PROVIDER_ENV_VARS[provider] ?? "env var"} on engine)`}
          className="flex-1 bg-surface-1 border border-border rounded-lg px-3 py-2 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50"
        />
      </div>

      {/* Submit row */}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={!task.trim() || isRunning || !engineOnline}
          className={cn(
            "px-5 py-2 rounded-lg font-mono text-sm font-semibold transition-colors",
            isRunning
              ? "bg-surface-3 text-text-muted cursor-not-allowed"
              : !task.trim() || !engineOnline
                ? "bg-surface-2 text-text-muted cursor-not-allowed"
                : "bg-accent text-surface-0 hover:bg-accent/80 cursor-pointer",
          )}
        >
          {isRunning ? "Running..." : dryRun ? "Recommend Stack" : "Run Validation"}
        </button>

        {isRunning && (
          <>
            <span className="font-mono text-xs text-text-secondary">
              {formatElapsed(elapsed)}
            </span>
            <button
              type="button"
              onClick={cancel}
              className="px-3 py-2 rounded-lg font-mono text-xs text-fail border border-fail/30 hover:bg-fail/10 transition-colors"
            >
              Cancel
            </button>
          </>
        )}

        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="ml-auto text-xs text-text-muted hover:text-text-secondary transition-colors"
        >
          {showAdvanced ? "Hide options" : "Options"}
        </button>
      </div>

      {/* Advanced options */}
      {showAdvanced && (
        <div className="grid grid-cols-2 gap-3 p-4 bg-surface-1 border border-border rounded-lg">
          <div>
            <label className="block text-xs text-text-muted mb-1">Model override</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g. claude-sonnet-4-20250514"
              className="w-full bg-surface-0 border border-border rounded px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Max attempts</label>
            <input
              type="number"
              value={maxAttempts}
              onChange={(e) => setMaxAttempts(Number(e.target.value))}
              min={0}
              max={10}
              className="w-full bg-surface-0 border border-border rounded px-3 py-1.5 font-mono text-xs text-text-primary focus:outline-none focus:border-accent/50"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Score threshold</label>
            <input
              type="number"
              value={scoreThreshold}
              onChange={(e) => setScoreThreshold(Number(e.target.value))}
              min={0}
              max={100}
              className="w-full bg-surface-0 border border-border rounded px-3 py-1.5 font-mono text-xs text-text-primary focus:outline-none focus:border-accent/50"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Timeout (seconds)</label>
            <input
              type="number"
              value={timeout}
              onChange={(e) => setTimeout_(Number(e.target.value))}
              min={30}
              max={3600}
              className="w-full bg-surface-0 border border-border rounded px-3 py-1.5 font-mono text-xs text-text-primary focus:outline-none focus:border-accent/50"
            />
          </div>
          <div className="col-span-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="accent-accent"
              />
              <span className="text-xs text-text-secondary">
                Dry run — recommend stack without executing
              </span>
            </label>
          </div>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="p-3 bg-fail/10 border border-fail/30 rounded-lg">
          <p className="text-sm text-fail font-mono">{error}</p>
        </div>
      )}

      {/* Engine offline warning */}
      {!engineOnline && (
        <div className="p-3 bg-warn/10 border border-warn/30 rounded-lg">
          <p className="text-sm text-warn font-mono">
            Engine offline — start the engine at localhost:4041
          </p>
        </div>
      )}
    </form>
  );
}
