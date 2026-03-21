"""Test Generator — generates and runs tests for execution output."""

import logging
import os
import re

import docker

from executor.docker_util import get_docker_client
from models.result import ExecutionResult
from models.task import TaskDefinition
from models.test_result import SingleTestResult, TestStatus, TestSuiteResult
from providers.base import LLMProvider, Message
from test_generator.prompts import TEST_GENERATION_SYSTEM, TEST_GENERATION_USER

logger = logging.getLogger(__name__)
_MAX_CONTEXT_FILES = 8
_MAX_CONTEXT_CHARS_PER_FILE = 1500
_MAX_CONTEXT_TOTAL_CHARS = 10000


class TestGenerator:
    """Generates tests from task spec + output artifacts, then runs them."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_and_run(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
    ) -> TestSuiteResult:
        """Generate tests and run them against the execution output."""
        test_code = await self.generate_tests(task, execution)
        return await self.write_and_run_tests(test_code, execution)

    async def generate_tests(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
    ) -> str:
        """Generate test code via LLM. Returns test code string."""
        logger.info("Generating tests for run %s", execution.run_id)
        return await self._generate_tests(task, execution)

    async def write_and_run_tests(
        self,
        test_code: str,
        execution: ExecutionResult,
    ) -> TestSuiteResult:
        """Write pre-generated test code to disk and run it in Docker."""
        test_dir = os.path.join(execution.output_dir, "..", "tests")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test_output.py")
        with open(test_file, "w") as f:
            f.write(test_code)

        logger.info("Generated test code (%d chars), running tests", len(test_code))

        result = await self._run_tests(test_dir, execution.output_dir)
        result.test_code = test_code
        return result

    async def _generate_tests(
        self,
        task: TaskDefinition,
        execution: ExecutionResult,
    ) -> str:
        """Use LLM to generate test code."""
        # Prepare artifact info (never show agent reasoning, only outputs)
        artifact_names, artifact_contents = _summarize_artifacts(execution.artifacts)

        messages = [
            Message(role="system", content=TEST_GENERATION_SYSTEM),
            Message(
                role="user",
                content=TEST_GENERATION_USER.format(
                    task_description=task.raw_input,
                    success_criteria="\n".join(f"- {c}" for c in task.success_criteria),
                    testable_assertions="\n".join(f"- {a}" for a in task.testable_assertions),
                    artifact_names=artifact_names or "No artifacts",
                    artifact_contents=artifact_contents or "No content",
                ),
            ),
        ]

        response = await self.provider.complete(messages=messages, max_tokens=4096)

        # Clean up response — remove markdown fences if present
        code = response.content.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]

        return code.strip()

    async def _run_tests(self, test_dir: str, output_dir: str) -> TestSuiteResult:
        """Run tests in an isolated Docker container."""
        try:
            client = get_docker_client()
        except docker.errors.DockerException as e:
            logger.error("Docker not available: %s", e)
            return TestSuiteResult(
                tests=[SingleTestResult(name="setup", status=TestStatus.ERROR, message=f"Docker not available: {e}")],
                total=1,
                errors=1,
                runner_output=f"Docker not available: {e}",
            )

        container = None
        try:
            image_tag = "validtr-test-runner:latest"
            self._ensure_test_runner_image(client, image_tag)

            logger.info("Running tests in isolated container")
            container = client.containers.run(
                image_tag,
                command=["python", "-m", "pytest", "/workspace/tests/",
                         "-v", "--tb=short", "--no-header", "-q"],
                volumes={
                    os.path.abspath(test_dir): {"bind": "/workspace/tests", "mode": "ro"},
                    os.path.abspath(output_dir): {"bind": "/workspace/output", "mode": "ro"},
                },
                environment={"VALIDTR_OUTPUT_DIR": "/workspace/output"},
                working_dir="/workspace/output",
                detach=True,
                network_mode="none",
            )

            container.wait(timeout=120)
            output = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")

            logger.debug("Test container output:\n%s", output[-2000:])
            return self._parse_pytest_output(output)

        except Exception as e:
            logger.error("Test execution failed: %s", e)
            return TestSuiteResult(
                tests=[SingleTestResult(name="container", status=TestStatus.ERROR, message=str(e))],
                total=1,
                errors=1,
                runner_output=f"Test execution failed: {e}",
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def _ensure_test_runner_image(self, client, tag: str) -> None:
        """Build the test runner image if it doesn't exist."""
        try:
            client.images.get(tag)
            return
        except docker.errors.ImageNotFound:
            pass

        logger.info("Building test runner image: %s", tag)
        import io
        import tarfile

        dockerfile_content = b"""\
FROM python:3.12-slim
RUN pip install --no-cache-dir pytest pytest-asyncio httpx requests
WORKDIR /workspace
"""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name="Dockerfile")
            info.size = len(dockerfile_content)
            tar.addfile(info, io.BytesIO(dockerfile_content))
        buf.seek(0)

        client.images.build(
            fileobj=buf,
            custom_context=True,
            tag=tag,
            rm=True,
        )

    def _parse_pytest_output(self, output: str) -> TestSuiteResult:
        """Parse pytest verbose output into a TestSuiteResult."""
        tests = []
        lines = output.split("\n")

        for line in lines:
            # Match pytest verbose output: "test_name PASSED" or "test_name FAILED"
            match = re.match(r"^(.+?)\s+(PASSED|FAILED|ERROR|SKIPPED)", line.strip())
            if match:
                name = match.group(1).strip()
                status_str = match.group(2)
                status_map = {
                    "PASSED": TestStatus.PASSED,
                    "FAILED": TestStatus.FAILED,
                    "ERROR": TestStatus.ERROR,
                    "SKIPPED": TestStatus.SKIPPED,
                }
                tests.append(SingleTestResult(
                    name=name,
                    status=status_map.get(status_str, TestStatus.ERROR),
                ))

        passed = sum(1 for t in tests if t.status == TestStatus.PASSED)
        failed = sum(1 for t in tests if t.status == TestStatus.FAILED)
        errors = sum(1 for t in tests if t.status == TestStatus.ERROR)
        skipped = sum(1 for t in tests if t.status == TestStatus.SKIPPED)

        return TestSuiteResult(
            tests=tests,
            total=len(tests),
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            runner_output=output,
        )


def _artifact_sort_key(name: str) -> tuple[int, str]:
    """Prioritize the files most likely to matter for generated tests."""
    if name == "manifest.json":
        return (0, name)
    if name.endswith(".py"):
        return (1, name)
    if name.endswith((".json", ".yaml", ".yml", ".toml")):
        return (2, name)
    return (3, name)


def _summarize_artifacts(artifacts: dict[str, str]) -> tuple[str, str]:
    """Return a bounded artifact list and content summary for test generation."""
    if not artifacts:
        return "No artifacts", "No content"

    selected_names: list[str] = []
    content_parts: list[str] = []
    total_chars = 0

    for name in sorted(artifacts, key=_artifact_sort_key)[:_MAX_CONTEXT_FILES]:
        content = artifacts[name]
        remaining = _MAX_CONTEXT_TOTAL_CHARS - total_chars
        if remaining <= 0:
            break

        truncated = content[: min(_MAX_CONTEXT_CHARS_PER_FILE, remaining)]
        selected_names.append(name)
        content_parts.append(f"\n--- {name} ---\n{truncated}\n")
        total_chars += len(truncated)

    return "\n".join(f"- {name}" for name in selected_names), "".join(content_parts)
