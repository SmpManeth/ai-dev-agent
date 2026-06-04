"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the coding agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    max_file_read_bytes: int = Field(default=100_000, alias="MAX_FILE_READ_BYTES")
    max_files_to_list: int = Field(default=500, alias="MAX_FILES_TO_LIST")
    max_search_results: int = Field(default=50, alias="MAX_SEARCH_RESULTS")
    prompts_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "prompts"
    )
    outputs_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "outputs"
    )

    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_owner: str | None = Field(default=None, alias="GITHUB_OWNER")
    github_repo: str | None = Field(default=None, alias="GITHUB_REPO")
    github_base_branch: str = Field(default="main", alias="GITHUB_BASE_BRANCH")

    workspace_root: Path | None = Field(default=None, alias="AI_AGENT_WORKSPACE_ROOT")
    auto_sync_repo: bool = Field(default=True, alias="AI_AGENT_AUTO_SYNC_REPO")

    jira_base_url: str | None = Field(default=None, alias="JIRA_BASE_URL")
    jira_email: str | None = Field(default=None, alias="JIRA_EMAIL")
    jira_api_token: str | None = Field(default=None, alias="JIRA_API_TOKEN")
    jira_project_key: str | None = Field(default=None, alias="JIRA_PROJECT_KEY")
    jira_label: str = Field(default="ai-fix", alias="JIRA_LABEL")
    jira_in_review_status: str = Field(default="In Review", alias="JIRA_IN_REVIEW_STATUS")

    @property
    def has_llm(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_github(self) -> bool:
        return bool(self.github_token)

    @property
    def has_jira(self) -> bool:
        return bool(
            self.jira_base_url
            and self.jira_email
            and self.jira_api_token
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def get_outputs_dir() -> Path:
    """Directory for generated patch artifacts (not the target repo)."""
    path = get_settings().outputs_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = get_settings().prompts_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
