"""Runtime configuration (phased plan §0.4).

All settings are environment-driven with the ``AAMT_`` prefix and can also be
placed in a local ``.env``. Nothing here requires an API key at import time —
only :func:`aamt.llm.provider.build_chat_model` does, and only when actually
invoking an agent.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AAMT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- storage --------------------------------------------------------
    data_dir: Path = Field(default=Path(".aamt"))
    """Where the project state DB, event log and checkpoints live."""

    workspace_dir: Path = Field(default=Path(".aamt/workspace"))
    """Parent dir for per-agent git worktrees / working copies."""

    # --- LLM provider --------------------------------------------------
    # openrouter (default) | anthropic | openai | azure_openai | ollama
    llm_provider: str = "openrouter"
    # dense model with reliable OpenAI-style function-calling on OpenRouter
    developer_model: str = "qwen/qwen-2.5-72b-instruct"
    coordinator_model: str = "qwen/qwen-2.5-72b-instruct"
    reviewer_model: str = "qwen/qwen-2.5-72b-instruct"
    # OpenRouter routes to the first available in this list (429/5xx failover)
    openrouter_fallback_models: str = (
        "mistralai/mistral-small-3.2-24b-instruct,qwen/qwen3-30b-a3b-instruct-2507"
    )
    llm_temperature: float = 0.0
    llm_max_tokens: int = 8192
    llm_request_timeout_s: float = 120.0    # hard cap on one HTTP call — a stalled
                                             # (non-erroring) response must become a
                                             # retryable timeout, not an infinite hang
    ollama_base_url: str = "http://localhost:11434"

    # OpenRouter (OpenAI-compatible). Keys are rotated round-robin and put on a
    # short cooldown on 429/402 so a rate-limited key steps aside automatically.
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_keys: str = ""            # comma-separated; else OPENROUTER_API_KEY_* env vars
    openrouter_referer: str = "https://github.com/aamt/autonomous-agile-team"
    openrouter_title: str = "aamt"
    openrouter_key_cooldown_s: float = 45.0
    openrouter_ignore_providers: str = "DeepInfra"   # comma-separated OpenRouter provider names to skip
    openrouter_probe_keys: bool = True      # classify keys paid/free once per process
    openrouter_free_model: str = "mistralai/mistral-small-3.2-24b-instruct:free"

    def resolved_openrouter_keys(self) -> list[str]:
        """Keys from AAMT_OPENROUTER_API_KEYS, else OPENROUTER_API_KEY[_N] env vars."""
        import os

        if self.openrouter_api_keys.strip():
            keys = [k.strip() for k in self.openrouter_api_keys.split(",") if k.strip()]
        else:
            keys = []
            for name, val in sorted(os.environ.items()):
                if name == "OPENROUTER_API_KEY" or name.startswith("OPENROUTER_API_KEY_"):
                    if val.strip():
                        keys.append(val.strip())
        # de-dupe, preserve order
        seen: set[str] = set()
        return [k for k in keys if not (k in seen or seen.add(k))]

    # --- agent runtime ------------------------------------------------
    max_concurrent_agents: int = 3
    max_task_retries: int = 3
    max_agent_steps: int = 40               # tool-call budget per task attempt
    agent_timeout_seconds: int = 900
    inter_task_seconds: float = 2.0         # pause between task executions (rate-limit hygiene)

    # --- tools / repository -----------------------------------------
    test_command: str = "pytest -q"
    build_command: str | None = None
    branch_prefix: str = "task/"
    commit_trailer: str = "Co-Authored-By: aamt-agent <agent@aamt.local>"
    allow_network_in_shell: bool = False

    # --- sprint / scrum -------------------------------------------
    sprint_length_ticks: int = 5            # standups per sprint (a "day" == a tick)
    standup_every_n_events: int = 12        # tick cadence when running head-less
    max_sprints: int = 6
    sprint_capacity_points: float = 20.0    # sum of estimates admitted per sprint
    sprint_max_tasks: int = 8               # hard cap on tasks per sprint
    default_task_estimate: float = 3.0      # used when the planner omits one

    # --- ceremonies / pipeline toggles (phases 6-9) -------------
    enable_review: bool = True              # reviewer agent gates integration
    enable_integration: bool = True         # merge task branches into main
    enable_standups: bool = True            # run a standup after each sprint tick
    enable_retro: bool = True               # generate a retrospective per sprint
    enable_llm_judge: bool = False          # LLM-grade acceptance criteria without a check cmd
    integration_target_branch: str = "main"

    # --- human-in-the-loop ---------------------------------------
    human_mode: str = "APPROVAL"            # AUTONOMOUS | APPROVAL | SUPERVISED
    control_file: str = "CONTROL"           # pause/resume sentinel under data_dir

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @property
    def state_db_path(self) -> Path:
        return self.data_dir / "project_state.db"

    @property
    def checkpoint_db_path(self) -> Path:
        return self.data_dir / "checkpoints.db"


_settings: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """Process-wide settings singleton."""
    global _settings
    if _settings is None or reload:
        _settings = Settings()
    return _settings
