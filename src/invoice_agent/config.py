"""Centralised application configuration.

All settings are read from environment variables (or a local ``.env`` file) and
validated by Pydantic. Import :func:`get_settings` anywhere a configuration
value is needed — it is cached so the environment is parsed only once.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, sourced from the environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "agentic-invoice-to-payment"
    environment: str = "local"
    log_level: str = "INFO"
    log_json: bool = True

    # --- PostgreSQL + PGVector ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "invoice_agent"
    postgres_user: str = "invoice_agent"
    postgres_password: str = "invoice_agent"

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "nomic-embed-text"

    # --- Arize Phoenix ---
    tracing_enabled: bool = True
    phoenix_collector_endpoint: str = "http://localhost:6006"

    # --- Mock / real ERP ---
    erp_base_url: str = "http://localhost:8001"
    erp_data_dir: str = "data/master"  # seed data for the mock ERP store

    # --- Email ingestion ---
    email_provider: str = "folder"  # folder | graph | gmail
    email_replay_dir: str = "data/inbox"

    # --- Matching tolerances (see also config/tolerances.yaml) ---
    price_tolerance_pct: float = Field(default=0.02, ge=0)
    qty_tolerance_pct: float = Field(default=0.0, ge=0)
    amount_tolerance_abs: float = Field(default=1.00, ge=0)

    @property
    def database_url(self) -> str:
        """SQLAlchemy / psycopg connection URL."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
