"""Scorer for code generation tasks."""

import json
import logging

from models.result import ExecutionResult
from models.score import DimensionScore, ScoreResult
from models.task import TaskDefinition
from models.test_result import TestSuiteResult
from providers.base import LLMProvider, Message
from scorer.context_compressor import compress_text
from scorer.prompts import COMPLETENESS_JUDGE_SYSTEM, COMPLETENESS_JUDGE_USER

logger = logging.getLogger(__name__)
_MAX_JUDGE_FILES = 6
_MAX_JUDGE_CHARS_PER_FILE = 1000
_MAX_JUDGE_TOTAL_CHARS = 6000

# Code task weights
TEST_PASSING_WEIGHT = 40
EXECUTION_WEIGHT = 25
SYNTAX_WEIGHT = 15
COMPLETENESS_WEIGHT = 20


class CodeScorer:
    """Scores code generation task output."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def score(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
        test_results: TestSuiteResult,
        threshold: float = 95.0,
    ) -> ScoreResult:
        """Compute composite score for a code generation task."""
        completeness_score = await self.judge_completeness(task, execution)
        return self._build_score(execution, test_results, completeness_score, threshold)

    def _deterministic_dimensions(
        self,
        execution: ExecutionResult,
        test_results: TestSuiteResult,
    ) -> list[DimensionScore]:
        """The three dimensions that need no LLM: test passing, execution, syntax."""
        return [
            # Test passing (40%)
            DimensionScore(
                name="Test passing",
                score=test_results.pass_rate * TEST_PASSING_WEIGHT,
                max_score=TEST_PASSING_WEIGHT,
                details=f"{test_results.passed}/{test_results.total} tests passed",
            ),
            # Execution (25%) — did the task run without errors?
            DimensionScore(
                name="Execution",
                score=EXECUTION_WEIGHT if execution.success else 0,
                max_score=EXECUTION_WEIGHT,
                details="Execution succeeded" if execution.success else f"Failed: {execution.error}",
            ),
            # Syntax validity (15%) — are the output files valid?
            DimensionScore(
                name="Syntax validity",
                score=self._check_syntax(execution.artifacts),
                max_score=SYNTAX_WEIGHT,
                details="Syntax check on output files",
            ),
        ]

    def _build_score(
        self,
        execution: ExecutionResult,
        test_results: TestSuiteResult,
        completeness_score: float,
        threshold: float,
    ) -> ScoreResult:
        """Assemble the composite score from the deterministic dimensions + completeness (20%)."""
        dimensions = self._deterministic_dimensions(execution, test_results)
        dimensions.append(DimensionScore(
            name="Completeness",
            score=completeness_score,
            max_score=COMPLETENESS_WEIGHT,
            details="LLM judge assessment",
        ))

        composite = sum(d.score for d in dimensions)
        result = ScoreResult(
            composite_score=composite,
            dimensions=dimensions,
            threshold=threshold,
        )
        result.check_passed()
        logger.info("Score: %.1f/100 (%s)", composite, "PASS" if result.passed else "FAIL")
        return result

    def _check_syntax(self, artifacts: dict[str, str]) -> float:
        """Check syntax validity of Python files in artifacts."""
        if not artifacts:
            return 0.0

        python_files = {k: v for k, v in artifacts.items() if k.endswith(".py")}
        if not python_files:
            # No Python files — give full marks if there are other files
            return SYNTAX_WEIGHT if artifacts else 0.0

        valid = 0
        for name, content in python_files.items():
            try:
                compile(content, name, "exec")
                valid += 1
            except SyntaxError:
                logger.debug("Syntax error in %s", name)

        ratio = valid / len(python_files) if python_files else 0
        return ratio * SYNTAX_WEIGHT

    async def score_with_precomputed_completeness(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
        test_results: TestSuiteResult,
        completeness_score: float,
        threshold: float = 95.0,
    ) -> ScoreResult:
        """Compute composite score using a pre-computed completeness score."""
        return self._build_score(execution, test_results, completeness_score, threshold)

    async def judge_completeness(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
    ) -> float:
        """Use LLM-as-judge to assess completeness."""
        artifact_summary = _summarize_artifacts_for_judge(execution.artifacts)

        messages = [
            Message(role="system", content=COMPLETENESS_JUDGE_SYSTEM),
            Message(
                role="user",
                content=COMPLETENESS_JUDGE_USER.format(
                    task_description=task.raw_input,
                    success_criteria="\n".join(f"- {c}" for c in task.success_criteria),
                    artifact_summary=artifact_summary or "No artifacts",
                ),
            ),
        ]

        try:
            response = await self.provider.complete_json(messages=messages, max_tokens=512)
            data = json.loads(response.content)
            raw_score = max(0, min(100, data.get("score", 50)))
            return (raw_score / 100) * COMPLETENESS_WEIGHT
        except Exception as e:
            logger.warning("Completeness judge failed: %s, defaulting to 50%%", e)
            return COMPLETENESS_WEIGHT * 0.5


def _summarize_artifacts_for_judge(artifacts: dict[str, str]) -> str:
    """Bound artifact content so the completeness judge stays fast.

    Tries headroom's semantic compression first (if enabled); falls back to blind
    per-file truncation, which can cut a file off mid-function but always works.
    """
    if not artifacts:
        return "No artifacts"

    parts: list[str] = []
    total_chars = 0

    for name in sorted(artifacts)[:_MAX_JUDGE_FILES]:
        remaining = _MAX_JUDGE_TOTAL_CHARS - total_chars
        if remaining <= 0:
            break

        content = artifacts[name]
        per_file_limit = min(_MAX_JUDGE_CHARS_PER_FILE, remaining)

        compressed = (
            compress_text(content, model_limit=per_file_limit)
            if len(content) > per_file_limit
            else None
        )
        body = compressed if compressed is not None else content[:per_file_limit]

        parts.append(f"\n--- {name} ---\n{body}\n")
        total_chars += len(body)

    return "".join(parts) or "No artifacts"
