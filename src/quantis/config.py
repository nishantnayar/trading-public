"""Central configuration, loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    # Source OHLC (bootstrap ETL)
    source_pg_url: str = Field(default="")
    source_ohlc_table: str = Field(default="")

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
