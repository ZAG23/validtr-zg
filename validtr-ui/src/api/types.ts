/** Mirrors the engine's RunRequest Pydantic model. */
export interface RunRequest {
  task: string;
  provider: string;
  model?: string | null;
  api_key?: string | null;
  search_api_key?: string | null;
  max_attempts?: number;
  score_threshold?: number;
  timeout?: number;
  dry_run?: boolean;
}

export interface DimensionScore {
  name: string;
  score: number;
  max_score: number;
  details: string;
}

export interface StackInfo {
  provider: string;
  model: string;
  framework: string | null;
  mcp_servers: string[];
  skills: string[];
  prompt_strategy: string;
  adjustment_notes: string[];
}

export interface AttemptInfo {
  attempt_number: number;
  score: number;
  dimensions: DimensionScore[];
  stack: StackInfo;
  adjustment_notes: string[];
}

/** Mirrors the engine's RunResponse Pydantic model. */
export interface RunResponse {
  run_id: string;
  score: number;
  passed: boolean;
  total_attempts: number;
  best_attempt: number;
  stack: StackInfo;
  dimensions: DimensionScore[];
  attempts: AttemptInfo[];
  artifact_count: number;
  artifacts: Record<string, string>;
}

/** Dry-run response shape. */
export interface DryRunResponse {
  task: Record<string, unknown>;
  recommendation: Record<string, unknown>;
}

/** Client-side run record with metadata for history. */
export interface StoredRun extends RunResponse {
  task: string;
  provider: string;
  timestamp: number;
}

export interface HealthResponse {
  status: string;
}

export interface EngineConfig {
  [key: string]: unknown;
}
