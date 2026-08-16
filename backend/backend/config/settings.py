from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # GitHub
    github_token: str = ""
    github_webhook_secret: str = ""
    github_repository: str = ""

    # Jira
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""

    # Tracing (Langfuse / LangSmith - not mutually exclusive, see integrations/tracing)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = "pr-reviewer"

    # App
    app_env: str = "development"
    backend_port: int = 8000
    frontend_port: int = 5173
    enable_test_execution: bool = False
    demo_mode: str = "auto"
    log_level: str = "INFO"
    database_url: str = f"sqlite+aiosqlite:///{(REPO_ROOT / 'data' / 'reviewer.db').as_posix()}"

    configs_dir: Path = REPO_ROOT / "configs"
    fixtures_dir: Path = REPO_ROOT / "tests" / "fixtures" / "demo_pr"

    @property
    def groq_mode(self) -> str:
        return "real" if self.groq_api_key else "mock"

    @property
    def github_mode(self) -> str:
        return "real" if self.github_token else "mock"

    @property
    def jira_mode(self) -> str:
        return "real" if (self.jira_base_url and self.jira_api_token) else "mock"

    @property
    def tracing_mode(self) -> str:
        backends = []
        if self.langfuse_public_key and self.langfuse_secret_key:
            backends.append("langfuse")
        if self.langsmith_api_key:
            backends.append("langsmith")
        return "+".join(backends) if backends else "noop"


@lru_cache
def get_settings() -> Settings:
    return Settings()
