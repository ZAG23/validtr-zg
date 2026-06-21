"""Run task API routes."""

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from analyzer.task_analyzer import TaskAnalyzer
from orchestrator import run_task
from providers.base import get_provider
from recommender.engine import RecommendationEngine

PROVIDER_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}

logger = logging.getLogger(__name__)
router = APIRouter()


class RunRequest(BaseModel):
    task: str
    provider: str = "anthropic"
    model: str | None = None
    api_key: str | None = None
    search_api_key: str | None = None
    max_attempts: int = 1
    score_threshold: float = 90.0
    timeout: int = 300
    dry_run: bool = False


class DimensionScoreResponse(BaseModel):
    name: str
    score: float
    max_score: float
    details: str = ""


class StackResponse(BaseModel):
    provider: str = ""
    model: str = ""
    framework: str | None = None
    mcp_servers: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    prompt_strategy: str = ""
    adjustment_notes: list[str] = Field(default_factory=list)


class AttemptResponse(BaseModel):
    attempt_number: int
    score: float
    dimensions: list[DimensionScoreResponse] = Field(default_factory=list)
    stack: StackResponse = Field(default_factory=StackResponse)
    adjustment_notes: list[str] = Field(default_factory=list)


class RunResponse(BaseModel):
    run_id: str
    score: float
    passed: bool
    total_attempts: int
    best_attempt: int
    stack: StackResponse
    dimensions: list[DimensionScoreResponse]
    attempts: list[AttemptResponse]
    artifact_count: int
    artifacts: dict[str, str]


@router.post("/run")
async def api_run_task(req: RunRequest):
    """Run the full validtr pipeline for a task."""
    # Validate provider early to return 400 instead of 500
    valid_providers = {"anthropic", "openai", "gemini"}
    if req.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {req.provider}. Choose from: {sorted(valid_providers)}",
        )

    # Resolve API key: request body > environment variable
    api_key = req.api_key
    if not api_key:
        env_var = PROVIDER_ENV_VARS.get(req.provider, "")
        api_key = os.environ.get(env_var, "") if env_var else ""

    if not api_key:
        env_var = PROVIDER_ENV_VARS.get(req.provider, f"<PROVIDER>_API_KEY")
        raise HTTPException(
            status_code=401,
            detail=f"No API key for {req.provider}. Pass it in the request or set {env_var} in the engine environment.",
        )

    if req.dry_run:
        return await _dry_run(req, api_key=api_key)

    try:
        result = await run_task(
            task=req.task,
            provider=req.provider,
            model=req.model,
            api_key=api_key,
            search_api_key=req.search_api_key,
            max_attempts=req.max_attempts,
            score_threshold=req.score_threshold,
            timeout=req.timeout,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        if "authentication" in str(e).lower() or "api_key" in str(e).lower():
            raise HTTPException(status_code=401, detail=f"Authentication failed: {e}") from e
        raise
    except Exception as e:
        err_type = type(e).__name__
        if "Authentication" in err_type or "AuthError" in err_type:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {e}") from e
        if "Permission" in err_type or "RateLimit" in err_type:
            raise HTTPException(status_code=429, detail=f"Rate limited or permission denied: {e}") from e
        raise

    # Build the best attempt's dimension breakdown
    best = None
    for a in result.attempts:
        if a.attempt_number == result.best_attempt:
            best = a
            break

    dimensions = []
    if best:
        dimensions = [
            DimensionScoreResponse(
                name=d.name, score=d.score, max_score=d.max_score, details=d.details,
            )
            for d in best.score.dimensions
        ]

    attempts_out = [
        AttemptResponse(
            attempt_number=a.attempt_number,
            score=a.score.composite_score,
            dimensions=[
                DimensionScoreResponse(
                    name=d.name, score=d.score, max_score=d.max_score, details=d.details,
                )
                for d in a.score.dimensions
            ],
            stack=StackResponse(
                provider=a.stack.provider,
                model=a.stack.model,
                framework=a.stack.framework,
                mcp_servers=a.stack.mcp_servers,
                skills=a.stack.skills,
                prompt_strategy=a.stack.prompt_strategy,
                adjustment_notes=a.stack.adjustment_notes,
            ),
            adjustment_notes=a.adjustment_notes,
        )
        for a in result.attempts
    ]

    return RunResponse(
        run_id=result.run_id,
        score=result.score,
        passed=result.passed,
        total_attempts=result.total_attempts,
        best_attempt=result.best_attempt,
        stack=StackResponse(
            provider=result.stack.provider,
            model=result.stack.model,
            framework=result.stack.framework,
            mcp_servers=result.stack.mcp_servers,
            skills=result.stack.skills,
            prompt_strategy=result.stack.prompt_strategy,
            adjustment_notes=result.stack.adjustment_notes,
        ),
        dimensions=dimensions,
        attempts=attempts_out,
        artifact_count=len(result.artifacts),
        artifacts=result.artifacts,
    )


async def _dry_run(req: RunRequest, api_key: str = ""):
    """Recommend a stack without executing."""
    try:
        llm = get_provider(req.provider, api_key=api_key, model=req.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        analyzer = TaskAnalyzer(provider=llm)
        task_def = await analyzer.analyze(req.task)

        recommender = RecommendationEngine(
            provider=llm,
            search_api_key=req.search_api_key,
        )
        stack = await recommender.recommend(task_def, preferred_provider=req.provider)
    except Exception as e:
        err_type = type(e).__name__
        if "Authentication" in err_type or "AuthError" in err_type:
            raise HTTPException(status_code=401, detail=f"Authentication failed: {e}") from e
        if "Permission" in err_type or "RateLimit" in err_type:
            raise HTTPException(status_code=429, detail=f"Rate limited or permission denied: {e}") from e
        raise

    return {
        "task": task_def.model_dump(),
        "recommendation": stack.model_dump(),
    }
