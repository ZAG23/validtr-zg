"""Scoring Engine — routes to task-type-specific scorers."""

import logging

from models.result import ExecutionResult
from models.score import ScoreResult
from models.task import TaskDefinition, TaskType
from models.test_result import TestSuiteResult
from providers.base import LLMProvider
from scorer.code_scorer import CodeScorer

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Routes scoring to the appropriate task-type scorer."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.scorers = {
            TaskType.CODE_GENERATION: CodeScorer(provider),
        }

    async def score(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
        test_results: TestSuiteResult,
        threshold: float = 95.0,
    ) -> ScoreResult:
        """Score execution output based on task type."""
        scorer = self.scorers.get(task.type)
        if not scorer:
            logger.warning("No scorer for task type %s, using code scorer", task.type)
            scorer = self.scorers[TaskType.CODE_GENERATION]

        return await scorer.score(task, execution, test_results, threshold)

    def _get_scorer(self, task: TaskDefinition):
        """Get the appropriate scorer for a task type."""
        scorer = self.scorers.get(task.type)
        if not scorer:
            logger.warning("No scorer for task type %s, using code scorer", task.type)
            scorer = self.scorers[TaskType.CODE_GENERATION]
        return scorer

    async def judge_completeness(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
    ) -> float:
        """Run only the completeness LLM judge. Returns the weighted score."""
        return await self._get_scorer(task).judge_completeness(task, execution)

    async def score_with_precomputed_completeness(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
        test_results: TestSuiteResult,
        completeness_score: float,
        threshold: float = 95.0,
    ) -> ScoreResult:
        """Score using a pre-computed completeness value."""
        return await self._get_scorer(task).score_with_precomputed_completeness(
            task, execution, test_results, completeness_score, threshold
        )
