"""Safety limits for execution."""

from pydantic import BaseModel


class SafetyLimits(BaseModel):
    """Configurable safety limits for task execution."""

    timeout_seconds: int = 300  # 5 minutes

    # Agent container isolation limits. The agent container runs LLM-generated
    # code with provider credentials injected, so it must be constrained.
    mem_limit: str = "2g"  # hard memory ceiling
    pids_limit: int = 512  # cap process/thread count (fork-bomb guard)
    cpus: float = 2.0  # CPU quota in cores
    drop_capabilities: bool = True  # cap_drop=ALL
    # Non-root UID:GID. "nobody:nogroup" on Debian-based images. Set to None to
    # run as the image's default user (not recommended).
    run_as_user: str | None = "65534:65534"
