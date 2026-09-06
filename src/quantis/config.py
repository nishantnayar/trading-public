"""Central configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = three levels up from this file (src/quantis/config.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    # Absolute path so .env resolves no matter the working directory (e.g. PyCharm).
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Postgres
    pghost: str = Field(default="localhost")
    pgport: int = Field(default=5432)
    pgdatabase: str = Field(default="quantis")
    pguser: str = Field(default="postgres")
    pgpassword: str = Field(default="")

    # Alpaca
    alpaca_api_key: str = Field(default="")
    alpaca_secret_key: str = Field(default="")
    alpaca_paper: bool = Field(default=True)

    # Execution: "simulated" never leaves this machine; "alpaca-paper" submits
    # to Alpaca's paper endpoint only. There is no live-trading value on purpose.
    quantis_broker: str = Field(default="simulated")

    # Prefect (distinct port/pool so it never collides with other local projects)
    prefect_api_url: str = Field(default="http://127.0.0.1:4201/api")
    prefect_work_pool: str = Field(default="quantis-ingestion")

    # FastAPI (Next.js on :3000 consumes this)
    api_cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")

    # SEC requires a contact-identifying User-Agent on every EDGAR request.
    edgar_user_agent: str = Field(default="Quantis Research nishant.nayar@gmail.com")

    @property
    def sqlalchemy_url(self) -> str:
        """psycopg (v3) SQLAlchemy URL for the project DB."""
        pw = f":{self.pgpassword}" if self.pgpassword else ""
        return (
            f"postgresql+psycopg://{self.pguser}{pw}"
            f"@{self.pghost}:{self.pgport}/{self.pgdatabase}"
        )

    @property
    def has_db_password(self) -> bool:
        return bool(self.pgpassword)


@lru_cache
def get_settings() -> Settings:
    return Settings()
