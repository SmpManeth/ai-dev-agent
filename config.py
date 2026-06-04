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

    @property
    def has_llm(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = get_settings().prompts_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
