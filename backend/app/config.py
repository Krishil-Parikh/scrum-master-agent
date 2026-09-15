"""
Central application configuration.

Everything the rest of the codebase needs to know about its environment goes
through a single `Settings` object built here (`get_settings()`), loaded once
from `backend/.env` via pydantic-settings. Nothing else in the codebase should
call `os.environ` directly, with one deliberate exception: the OpenRouter
key *pool* (`OPENROUTER_API_KEY_1`, `_2`, ... an unbounded, numbered set
pydantic-settings can't model as a fixed field) is discovered straight from
`os.environ` in `llm/openrouter_client.py`. pydantic-settings' `env_file`
loading only populates its own Settings object, not the process
environment -- so this module explicitly loads `.env` into `os.environ` too
via `python-dotenv`, which is what makes that key-pool discovery possible at
all. Import `app.config` before anything that needs env vars to be present.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Populate os.environ from backend/.env as an explicit side effect of
# importing this module -- see the module docstring for why this is
# necessary in addition to pydantic-settings' own (process-env-only)
# env_file loading below.
load_dotenv(BACKEND_DIR / ".env")
# backend/project_data -- persisted project memory (Markdown + JSON state)
PROJECT_DATA_DIR = BACKEND_DIR / "project_data"
# backend/workspace -- isolated per-agent Git workspaces for the demo project
WORKSPACE_DIR = BACKEND_DIR / "workspace"
# backend/app/skills/library -- the shared skill markdown library
SKILLS_DIR = BACKEND_DIR / "app" / "skills" / "library"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenRouter / LLM ---
    # Individual OPENROUTER_API_KEY_1..N env vars are collected separately in
    # openrouter_client.py (pydantic-settings can't easily model an unbounded
    # set of numbered keys), so only the shared, non-secret bits live here.
    openrouter_model: str = "mistralai/mistral-small-3.2-24b-instruct"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "http://localhost:5173"
    openrouter_app_name: str = "AI Dev Pod"
    llm_temperature: float = 0.4
    llm_max_tokens: int = 2000
    llm_request_timeout_seconds: float = 60.0
    llm_max_retries_per_call: int = 4

    # --- App ---
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Demo project / Git ---
    demo_project_git_remote: str = ""
    demo_project_name: str = "AI Task Management Platform"

    # --- SME ---
    sme_mode: str = "auto"  # "auto" | "human"

    # --- Testing (scaling roadmap #5) ---
    # Off by default: enabling this makes the testing phase `pip install`
    # whatever the LLM-generated requirements.txt says, into a per-project
    # venv, before running pytest -- which lets tests actually EXECUTE
    # (catching real logic/integration bugs) instead of only ever being
    # syntax-checked. That's a real capability upgrade, but it also means
    # automatically running `pip install` against arbitrary
    # model-generated package names with no human review first -- a
    # supply-chain risk the PRD's own security requirements (§34: "Restrict
    # destructive commands") argue against doing silently. Turn on
    # deliberately, not as a side effect of upgrading.
    enable_dependency_install_for_tests: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process. Cached deliberately: env vars don't
    change mid-run, and re-parsing the .env file on every access would be
    wasted work sprinkled across every module that needs config."""
    return Settings()
