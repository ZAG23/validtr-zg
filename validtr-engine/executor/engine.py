"""Execution Engine — runs tasks inside Docker containers or directly."""

import json
import logging
import os
import re
import shutil
import time

import docker

from executor.docker_util import BASE_AGENT_IMAGE, ensure_base_images, get_docker_client
from executor.safety import SafetyLimits
from executor.trace import TraceCollector
from models.result import ExecutionResult
from models.stack import MCPTransport, StackRecommendation
from models.task import TaskDefinition
from providers.base import LLMProvider, Message
from provisioner.compose_generator import ComposeGenerator
from provisioner.credentials import resolve_credentials

_FILE_PATTERN = re.compile(r'--- FILE: (.+?) ---\n(.*?)\n--- END FILE ---', re.DOTALL)

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Runs a task in a provisioned Docker environment and captures results."""

    def __init__(
        self,
        safety_limits: SafetyLimits | None = None,
        output_base: str | None = None,
    ):
        self.safety = safety_limits or SafetyLimits()
        self.compose_gen = ComposeGenerator(output_base=output_base)
        self._docker_client = None

    @property
    def docker_client(self):
        """Lazily initialize Docker client (only needed for container execution)."""
        if self._docker_client is None:
            self._docker_client = get_docker_client()
            ensure_base_images(self._docker_client)
        return self._docker_client

    async def execute(
        self,
        run_id: str,
        task: TaskDefinition,
        stack: StackRecommendation,
        api_keys: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """Execute a task in a Docker container."""
        trace = TraceCollector()
        logger.info("Starting execution for run %s", run_id)

        try:
            # Resolve credentials
            credentials = resolve_credentials(stack, api_keys)

            # Generate Docker Compose config and supporting files
            run_dir, compose_path = self.compose_gen.generate(run_id, stack, credentials)

            # Write task and stack definitions to workspace
            workspace_dir = os.path.join(run_dir, "workspace")
            with open(os.path.join(workspace_dir, "task.json"), "w") as f:
                json.dump(task.model_dump(), f, indent=2)
            with open(os.path.join(workspace_dir, "stack.json"), "w") as f:
                json.dump(stack.model_dump(), f, indent=2)

            # Determine if we need a per-run image (MCP servers) or can use the base
            has_mcp = any(
                s.transport == MCPTransport.STDIO for s in stack.mcp_servers
            )
            image_tag = self._resolve_agent_image(run_dir, run_id, has_mcp)

            # Build and run agent container
            artifacts = await self._run_agent_container(
                run_dir, run_id, image_tag, credentials, stack, trace
            )

            execution_trace = trace.finalize()

            return ExecutionResult(
                run_id=run_id,
                artifacts=artifacts,
                trace=execution_trace,
                output_dir=os.path.join(workspace_dir, "output"),
                success=True,
            )

        except Exception as e:
            logger.error("Execution failed for run %s: %s", run_id, e)
            execution_trace = trace.finalize()
            execution_trace.error = str(e)
            return ExecutionResult(
                run_id=run_id,
                trace=execution_trace,
                success=False,
                error=str(e),
            )

    async def execute_direct(
        self,
        run_id: str,
        task: TaskDefinition,
        stack: StackRecommendation,
        provider: LLMProvider,
    ) -> ExecutionResult:
        """Execute a task directly via LLM (no Docker). Single-shot generation."""
        trace = TraceCollector()
        logger.info("Starting direct execution for run %s", run_id)

        output_base = self.compose_gen.output_base
        run_dir = os.path.join(output_base, run_id)
        output_dir = os.path.join(run_dir, "workspace", "output")
        os.makedirs(output_dir, exist_ok=True)

        try:
            criteria = "\n".join(f"- {c}" for c in task.success_criteria)
            strategy = stack.prompt_strategy.strip() or "Implement the minimum working solution first, then refine details."
            framework = stack.framework.name or "none"
            skills = ", ".join(stack.skills) if stack.skills else "none"
            system_prompt = (
                "You are an AI agent tasked with completing a software engineering task.\n\n"
                f"Task: {task.raw_input}\n\n"
                f"Success Criteria:\n{criteria}\n\n"
                f"Recommended framework: {framework}\n"
                f"Recommended skills: {skills}\n"
                f"Execution strategy: {strategy}\n\n"
                "Output ALL files in this exact format (one block per file):\n\n"
                "--- FILE: path/to/file ---\n"
                "file content here\n"
                "--- END FILE ---\n\n"
                "Include a manifest.json listing all files you created.\n"
                "Generate ALL files in a single response. Do not explain — just output the file blocks."
            )

            start = time.time()
            response = await provider.complete(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=f"Complete this task: {task.raw_input}"),
                ],
                max_tokens=12288,
            )
            duration_ms = int((time.time() - start) * 1000)

            trace.record_llm_call(
                provider=provider.provider_name,
                model=provider.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                duration_ms=duration_ms,
            )

            # Parse and write file blocks
            file_blocks = _FILE_PATTERN.findall(response.content)
            if not file_blocks:
                # Write raw output as fallback
                file_blocks = [("output.py", response.content)]

            for path, content in file_blocks:
                path = path.strip()
                full_path = os.path.realpath(os.path.join(output_dir, path))
                base_real = os.path.realpath(output_dir)
                if not full_path.startswith(base_real + os.sep) and full_path != base_real:
                    logger.warning("Blocked path traversal: %s", path)
                    continue
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(content)

            logger.info("Direct execution wrote %d files in %dms", len(file_blocks), duration_ms)

            # Collect artifacts
            artifacts = {}
            for root, _, files in os.walk(output_dir):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, output_dir)
                    try:
                        with open(filepath) as f:
                            artifacts[rel_path] = f.read()
                    except (UnicodeDecodeError, OSError):
                        artifacts[rel_path] = "<binary file>"

            return ExecutionResult(
                run_id=run_id,
                artifacts=artifacts,
                trace=trace.finalize(),
                output_dir=output_dir,
                success=True,
            )

        except Exception as e:
            logger.error("Direct execution failed for run %s: %s", run_id, e)
            execution_trace = trace.finalize()
            execution_trace.error = str(e)
            return ExecutionResult(
                run_id=run_id,
                trace=execution_trace,
                output_dir=output_dir,
                success=False,
                error=str(e),
            )

    def _resolve_agent_image(self, run_dir: str, run_id: str, has_mcp: bool) -> str:
        """Return the image tag to use. Builds a per-run image only if MCP servers need installing."""
        if not has_mcp:
            return BASE_AGENT_IMAGE

        tag = f"validtr-agent-{run_id}"
        logger.info("Building per-run agent image for MCP servers: %s", tag)
        try:
            self.docker_client.images.build(
                path=run_dir,
                dockerfile="Dockerfile.agent",
                tag=tag,
                rm=True,
            )
        except docker.errors.BuildError as e:
            raise RuntimeError(f"Failed to build agent image: {e}") from e
        return tag

    def _container_security_kwargs(self, environment: dict[str, str]) -> dict:
        """Build resource and isolation limits for the agent container.

        The agent container runs LLM-generated code with provider credentials
        injected, so it gets hard memory/PID/CPU caps, all Linux capabilities
        dropped, no privilege escalation, and a non-root user. Rootfs is NOT
        made read-only: MCP stdio servers (npx/uvx) need a writable cache, so
        we give them a tmpfs at /tmp and point HOME there instead.
        """
        kwargs: dict = {
            "mem_limit": self.safety.mem_limit,
            "memswap_limit": self.safety.mem_limit,  # equal to mem_limit disables swap
            "pids_limit": self.safety.pids_limit,
            "nano_cpus": int(self.safety.cpus * 1_000_000_000),
            "security_opt": ["no-new-privileges:true"],
            "tmpfs": {"/tmp": "rw,size=256m,mode=1777"},
        }
        if self.safety.drop_capabilities:
            kwargs["cap_drop"] = ["ALL"]
        if self.safety.run_as_user:
            kwargs["user"] = self.safety.run_as_user
            # Non-root user has no home dir in the image; route caches to tmpfs.
            environment.setdefault("HOME", "/tmp")
        return kwargs

    async def _run_agent_container(
        self,
        run_dir: str,
        run_id: str,
        image_tag: str,
        credentials: dict[str, str],
        stack: StackRecommendation,
        trace: TraceCollector,
    ) -> dict[str, str]:
        """Run the agent container. Returns artifacts dict."""
        start = time.time()

        workspace_dir = os.path.join(run_dir, "workspace")
        entrypoint_path = os.path.join(run_dir, "entrypoint.py")
        agent_loop_path = os.path.join(run_dir, "agent_loop.py")

        environment = {
            "VALIDTR_RUN_ID": run_id,
            "VALIDTR_PROVIDER": stack.llm.provider,
            "VALIDTR_MODEL": stack.llm.model,
        }
        environment.update(credentials)

        volumes = {
            workspace_dir: {"bind": "/workspace", "mode": "rw"},
            entrypoint_path: {"bind": "/app/entrypoint.py", "mode": "ro"},
            agent_loop_path: {"bind": "/app/agent_loop.py", "mode": "ro"},
        }

        run_kwargs = self._container_security_kwargs(environment)

        logger.info("Running agent container (image: %s)", image_tag)
        container = None
        try:
            container = self.docker_client.containers.run(
                image_tag,
                detach=True,
                volumes=volumes,
                environment=environment,
                **run_kwargs,
            )

            result = container.wait(timeout=self.safety.timeout_seconds)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            logger.info("Agent container finished with status %s", result.get("StatusCode", -1))
            logger.debug("Container logs:\n%s", logs[-2000:])

        except Exception as e:
            logger.error("Container execution failed: %s", e)
            raise
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

        duration_ms = int((time.time() - start) * 1000)
        trace.record_llm_call(
            provider="docker",
            model=image_tag,
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
        )

        # Collect artifacts from output directory
        artifacts = {}
        output_dir = os.path.join(workspace_dir, "output")
        if os.path.exists(output_dir):
            for root, _dirs, files in os.walk(output_dir):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, output_dir)
                    try:
                        with open(filepath) as f:
                            artifacts[rel_path] = f.read()
                    except (UnicodeDecodeError, OSError):
                        artifacts[rel_path] = "<binary file>"

        logger.info("Collected %d artifacts", len(artifacts))
        return artifacts

    async def cleanup(self, run_id: str) -> None:
        """Reclaim the per-run image and working directory for a run.

        Only touches Docker if a client was actually created (the direct
        execution fast path never uses Docker), so cleanup after a direct run
        won't spin up a client just to remove a non-existent image.
        """
        # Remove the per-run agent image, if one was built (MCP path only).
        if self._docker_client is not None:
            tag = f"validtr-agent-{run_id}"
            try:
                self._docker_client.images.remove(tag, force=True)
            except docker.errors.ImageNotFound:
                pass
            except docker.errors.APIError as e:
                logger.warning("Cleanup failed for image %s: %s", tag, e)

        # Remove the working directory (compose files, workspace, artifacts).
        run_dir = os.path.join(self.compose_gen.output_base, run_id)
        shutil.rmtree(run_dir, ignore_errors=True)
