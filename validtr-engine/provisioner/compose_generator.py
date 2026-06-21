"""Generates Docker Compose configurations from StackRecommendations."""

import logging
import os
import tempfile

import yaml

from models.stack import MCPTransport, StackRecommendation

logger = logging.getLogger(__name__)


class ComposeGenerator:
    """Generates Docker Compose YAML and supporting files for a run."""

    def __init__(self, output_base: str | None = None):
        self.output_base = output_base or os.path.join(tempfile.gettempdir(), "validtr-runs")

    def generate(
        self,
        run_id: str,
        stack: StackRecommendation,
        credentials: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        """Generate Docker Compose config. Returns (run_dir, compose_file_path)."""
        run_dir = os.path.join(self.output_base, run_id)
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(os.path.join(run_dir, "workspace"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "workspace", "tests"), exist_ok=True)

        compose = self._build_compose(run_id, stack, run_dir, credentials or {})

        compose_path = os.path.join(run_dir, "docker-compose.yml")
        with open(compose_path, "w") as f:
            yaml.dump(compose, f, default_flow_style=False)

        # Write agent scripts (mounted as volumes at runtime, not baked into image)
        self._write_entrypoint(run_dir)
        self._write_agent_loop(run_dir, stack)

        logger.info("Generated compose config at %s", compose_path)
        return run_dir, compose_path

    def _build_compose(
        self,
        run_id: str,
        stack: StackRecommendation,
        run_dir: str,
        credentials: dict[str, str],
    ) -> dict:
        """Build the Docker Compose dictionary."""
        services = {}

        # Agent container
        agent_env = {
            "VALIDTR_RUN_ID": run_id,
            "VALIDTR_PROVIDER": stack.llm.provider,
            "VALIDTR_MODEL": stack.llm.model,
        }
        # Inject credentials
        for key, value in credentials.items():
            agent_env[key] = value

        # Build MCP install commands for the Dockerfile
        mcp_installs = []
        for server in stack.mcp_servers:
            if server.transport == MCPTransport.STDIO:
                mcp_installs.append(f"RUN {server.install} || true")

        agent_dockerfile = self._generate_agent_dockerfile(mcp_installs)
        dockerfile_path = os.path.join(run_dir, "Dockerfile.agent")
        with open(dockerfile_path, "w") as f:
            f.write(agent_dockerfile)

        # Use base image directly when no MCP servers, per-run build otherwise
        if mcp_installs:
            services["agent"] = {
                "build": {
                    "context": run_dir,
                    "dockerfile": "Dockerfile.agent",
                },
                "environment": agent_env,
                "volumes": [
                    f"{os.path.join(run_dir, 'workspace')}:/workspace",
                    f"{os.path.join(run_dir, 'entrypoint.py')}:/app/entrypoint.py:ro",
                    f"{os.path.join(run_dir, 'agent_loop.py')}:/app/agent_loop.py:ro",
                ],
                "networks": ["validtr-net"],
            }
        else:
            services["agent"] = {
                "image": "validtr-agent-base:latest",
                "environment": agent_env,
                "volumes": [
                    f"{os.path.join(run_dir, 'workspace')}:/workspace",
                    f"{os.path.join(run_dir, 'entrypoint.py')}:/app/entrypoint.py:ro",
                    f"{os.path.join(run_dir, 'agent_loop.py')}:/app/agent_loop.py:ro",
                ],
                "networks": ["validtr-net"],
            }

        # MCP server containers (streamable-http only)
        for server in stack.mcp_servers:
            if server.transport == MCPTransport.STREAMABLE_HTTP:
                service_name = f"mcp-{server.name}"
                services[service_name] = {
                    "image": f"mcp-{server.name}:latest",
                    "networks": ["validtr-net"],
                    "environment": {},
                }
                if server.credentials != "none" and server.credentials in credentials:
                    services[service_name]["environment"][server.credentials] = credentials[server.credentials]

        # Test runner container — uses pre-built base image
        services["test-runner"] = {
            "image": "validtr-test-runner:latest",
            "volumes": [
                f"{os.path.join(run_dir, 'workspace')}:/workspace:ro",
            ],
            "networks": ["validtr-net"],
            "depends_on": ["agent"],
        }

        return {
            "version": "3.8",
            "services": services,
            "networks": {
                "validtr-net": {"driver": "bridge"},
            },
        }

    def _generate_agent_dockerfile(self, mcp_installs: list[str]) -> str:
        """Generate the agent Dockerfile with MCP server installations."""
        template_path = os.path.join(
            os.path.dirname(__file__), "templates", "agent.Dockerfile"
        )
        with open(template_path) as f:
            template = f.read()

        # Replace the MCP install placeholder
        mcp_section = "\n".join(mcp_installs) if mcp_installs else "# No MCP servers to install"
        return template.replace("# MCP_INSTALL_COMMANDS placeholder", mcp_section)

    def _write_entrypoint(self, run_dir: str) -> None:
        """Write the agent container entrypoint script."""
        entrypoint = '''"""Agent container entrypoint."""
import json
import os
import sys

def main():
    run_id = os.environ.get("VALIDTR_RUN_ID", "unknown")
    print(f"[validtr] Starting agent for run {run_id}")

    # Read task definition from mounted workspace
    task_path = "/workspace/task.json"
    if not os.path.exists(task_path):
        print("[validtr] ERROR: No task.json found in /workspace")
        sys.exit(1)

    with open(task_path) as f:
        task = json.load(f)

    # Read stack config
    stack_path = "/workspace/stack.json"
    if not os.path.exists(stack_path):
        print("[validtr] ERROR: No stack.json found in /workspace")
        sys.exit(1)

    with open(stack_path) as f:
        stack = json.load(f)

    # Run the agent loop
    from agent_loop import run_agent
    run_agent(task, stack)

if __name__ == "__main__":
    main()
'''
        with open(os.path.join(run_dir, "entrypoint.py"), "w") as f:
            f.write(entrypoint)

    def _write_agent_loop(self, run_dir: str, stack: StackRecommendation) -> None:
        """Write the agent loop script that runs inside the container."""
        agent_loop = '''"""Single-shot code generation agent for validtr."""
import json
import os
import re
import sys

FILE_PATTERN = r'--- FILE: (.+?) ---\\n(.*?)\\n--- END FILE ---'

def get_llm_client():
    """Initialize the LLM client based on environment."""
    provider = os.environ.get("VALIDTR_PROVIDER", "anthropic")
    model = os.environ.get("VALIDTR_MODEL", "claude-sonnet-4-20250514")

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        return client, model, provider
    elif provider == "openai":
        import openai
        client = openai.OpenAI()
        return client, model, provider
    elif provider == "gemini":
        from google import genai
        client = genai.Client()
        return client, model, provider
    else:
        raise ValueError(f"Unknown provider: {provider}")

def run_agent(task: dict, stack: dict):
    """Run single-shot code generation."""
    client, model, provider = get_llm_client()
    framework_name = (stack.get("framework") or {}).get("name") or "none"
    prompt_strategy = stack.get("prompt_strategy") or "Implement the minimum working solution first, then refine details."
    skills = ", ".join(stack.get("skills", [])) or "none"

    system_prompt = f"""You are an AI agent tasked with completing a software engineering task.
You must produce working output files.

Task: {task.get('raw_input', '')}

Success Criteria:
{chr(10).join('- ' + c for c in task.get('success_criteria', []))}

Recommended framework: {framework_name}
Recommended skills: {skills}
Execution strategy: {prompt_strategy}

Output ALL files in this exact format (one block per file):

--- FILE: path/to/file ---
file content here
--- END FILE ---

Include a manifest.json listing all files you created.
Generate ALL files in a single response. Do not explain — just output the file blocks."""

    os.makedirs("/workspace/output", exist_ok=True)

    if provider == "anthropic":
        text, in_tok, out_tok = _generate_anthropic(client, model, system_prompt, task)
    elif provider == "openai":
        text, in_tok, out_tok = _generate_openai(client, model, system_prompt, task)
    elif provider == "gemini":
        text, in_tok, out_tok = _generate_gemini(client, model, system_prompt, task)
    else:
        text, in_tok, out_tok = "", 0, 0

    _parse_and_write_files(text)
    _write_harness_report(provider, client, model, system_prompt, stack, in_tok, out_tok)

def _generate_anthropic(client, model, system_prompt, task):
    """Single-shot generation with Anthropic. Returns (text, input_tokens, output_tokens)."""
    response = client.messages.create(
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Complete this task: {task.get('raw_input', '')}"}],
        max_tokens=12288,
    )
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text
    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "input_tokens", 0) if usage else 0
    out_tok = getattr(usage, "output_tokens", 0) if usage else 0
    print("[validtr] Agent completed task (single-shot)")
    return text, in_tok, out_tok

def _generate_openai(client, model, system_prompt, task):
    """Single-shot generation with OpenAI. Returns (text, input_tokens, output_tokens)."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Complete this task: {task.get('raw_input', '')}"},
        ],
        max_tokens=12288,
    )
    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    print("[validtr] Agent completed task (single-shot)")
    return text, in_tok, out_tok

def _generate_gemini(client, model, system_prompt, task):
    """Single-shot generation with Gemini. Returns (text, input_tokens, output_tokens)."""
    from google.genai import types
    response = client.models.generate_content(
        model=model,
        contents=[f"{system_prompt}\\n\\nTask: {task.get('raw_input', '')}"],
        config=types.GenerateContentConfig(max_output_tokens=12288),
    )
    text = response.text or ""
    um = getattr(response, "usage_metadata", None)
    in_tok = getattr(um, "prompt_token_count", 0) if um else 0
    out_tok = getattr(um, "candidates_token_count", 0) if um else 0
    print("[validtr] Agent completed task (single-shot)")
    return text, in_tok, out_tok

def _count_tokens(provider, client, model, text):
    """Count tokens for text using the provider tokenizer; fall back to chars/4."""
    try:
        if provider == "anthropic":
            msgs = [{"role": "user", "content": text}]
            return client.messages.count_tokens(model=model, messages=msgs).input_tokens
        if provider == "openai":
            import tiktoken
            enc = tiktoken.get_encoding("o200k_base")
            return len(enc.encode(text))
        if provider == "gemini":
            r = client.models.count_tokens(model=model, contents=[text])
            return r.total_tokens
    except Exception as e:
        print(f"[validtr] token count fallback ({e})")
    return max(1, len(text) // 4) if text else 0

def _write_harness_report(provider, client, model, system_prompt, stack, in_tok, out_tok):
    """Write harness-report.json for token projection. Never breaks the run."""
    try:
        system_prompt_tokens = _count_tokens(provider, client, model, system_prompt)
        mcp_servers = stack.get("mcp_servers", [])
        mcp_server_names = [s.get("name", "") for s in mcp_servers if s.get("name")]
        skill_names = list(stack.get("skills", []))
        report = {
            "system_prompt_tokens": system_prompt_tokens,
            "measured_input_tokens": in_tok,
            "measured_output_tokens": out_tok,
            "turns": 1,
            "mcp_server_names": mcp_server_names,
            "skill_names": skill_names,
        }
        with open("/workspace/output/harness-report.json", "w") as f:
            json.dump(report, f)
        print(f"[validtr] Wrote harness-report.json (system={system_prompt_tokens} tokens)")
    except Exception as e:
        print(f"[validtr] Could not write harness-report.json ({e})")

def _parse_and_write_files(text):
    """Parse structured file blocks and write them to /workspace/output/."""
    file_blocks = re.findall(FILE_PATTERN, text, re.DOTALL)
    for path, content in file_blocks:
        _write_file(path.strip(), content)

    if not file_blocks:
        print("[validtr] No file blocks found, writing raw output")
        _write_file("output.py", text)

    print(f"[validtr] Wrote {len(file_blocks)} files")

def _write_file(path: str, content: str) -> None:
    """Write a file to /workspace/output/ with path traversal protection."""
    base_dir = os.path.realpath("/workspace/output")
    full_path = os.path.realpath(os.path.join(base_dir, path))
    if not full_path.startswith(base_dir + os.sep) and full_path != base_dir:
        print(f"[validtr] BLOCKED path traversal attempt: {path}")
        return
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)
    print(f"[validtr] Wrote file: {path}")
'''
        with open(os.path.join(run_dir, "agent_loop.py"), "w") as f:
            f.write(agent_loop)
