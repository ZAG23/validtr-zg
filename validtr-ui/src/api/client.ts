import type { RunRequest, RunResponse, HealthResponse, EngineConfig } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(res.status, message);
  }

  return res.json() as Promise<T>;
}

export async function runTask(
  req: RunRequest,
  signal?: AbortSignal,
): Promise<RunResponse> {
  return request<RunResponse>("/api/run", {
    method: "POST",
    body: JSON.stringify(req),
    signal,
  });
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getConfig(): Promise<EngineConfig> {
  return request<EngineConfig>("/api/config");
}
