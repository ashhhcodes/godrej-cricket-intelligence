"""
Configuration loading and validation module.
Uses Pydantic and python-dotenv to enforce environment boundaries,
prevent credential leaks, and guarantee safe defaults.
"""

import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Automatically search for .env in project root
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)


class AppConfig(BaseModel):
    """
    Application configuration with strict validation.
    Default mode is ALWAYS 'fixture_replay' to protect API quota.
    """
    model_config = ConfigDict(validate_assignment=True)

    # Engine execution mode
    ingestion_mode: Literal["fixture_replay", "live"] = Field(
        default="fixture_replay",
        description="Ingestion execution mode: 'fixture_replay' or 'live'"
    )
    allow_live_api: bool = Field(
        default=False,
        description="Explicit security opt-in required to invoke external CricAPI"
    )

    # CricketData / CricAPI parameters
    cricapi_key: str = Field(
        default="",
        description="CricketData.org API key from .env"
    )
    cricapi_base_url: str = Field(
        default="https://api.cricapi.com/v1",
        description="Base URL for CricAPI v1 endpoints"
    )
    api_daily_quota_limit: int = Field(
        default=100,
        ge=1,
        description="Daily request ceiling (Lifetime Free plan default: 100)"
    )
    api_safety_margin_hits: int = Field(
        default=10,
        ge=1,
        description="Reserved hit buffer to prevent breaching the quota ceiling"
    )
    api_poll_interval_seconds: int = Field(
        default=120,
        ge=10,
        description="Interval between external live API requests in seconds"
    )

    # Simulation / Replay settings
    simulation_speed_seconds: int = Field(
        default=30,
        ge=1,
        description="Seconds to wait between advancing replay states"
    )
    fixture_path: str = Field(
        default=str(ROOT_DIR / "tests" / "fixtures" / "cricsheet_t20_match.json"),
        description="Path to offline historical fixture dataset"
    )
    target_match_id: str = Field(
        default="",
        description="Optional specific match ID to track in live mode"
    )

    # PostgreSQL database settings
    postgres_host: str = Field(
        default="localhost",
        description="PostgreSQL server hostname"
    )
    postgres_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="PostgreSQL server port"
    )
    postgres_db: str = Field(
        default="godrej_cricket_db",
        description="Target database name"
    )
    postgres_user: str = Field(
        default="postgres",
        description="Database username"
    )
    postgres_password: str = Field(
        default="",
        description="Database password"
    )

    # Observability
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR"
    )
    log_file_path: str = Field(
        default="logs/ingestion.log",
        description="Optional path to structured log file"
    )

    @model_validator(mode="after")
    def validate_live_mode_security(self) -> "AppConfig":
        """
        Enforce strict security: Live API mode CANNOT run without explicit opt-in.
        """
        if self.ingestion_mode == "live":
            if not self.allow_live_api:
                raise ValueError(
                    "Security Violation: 'ingestion_mode' is set to 'live' but 'allow_live_api' is False. "
                    "Live API calls require explicit opt-in via ALLOW_LIVE_API=true in .env to protect quota."
                )
            if not self.cricapi_key or self.cricapi_key.startswith("your_"):
                raise ValueError(
                    "Configuration Error: 'ingestion_mode' is 'live' but CRICAPI_KEY is missing or invalid in .env."
                )
        return self

    @property
    def postgres_connection_string(self) -> str:
        """
        Returns connection string for PostgreSQL (never print or log directly).
        """
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password}"
        )

    def safe_summary(self) -> dict:
        """
        Returns a redacted dictionary of configuration parameters safe for logging.
        """
        return {
            "ingestion_mode": self.ingestion_mode,
            "allow_live_api": self.allow_live_api,
            "cricapi_key": "[MASKED]" if self.cricapi_key else "[NOT_SET]",
            "cricapi_base_url": self.cricapi_base_url,
            "api_daily_quota_limit": self.api_daily_quota_limit,
            "api_safety_margin_hits": self.api_safety_margin_hits,
            "api_poll_interval_seconds": self.api_poll_interval_seconds,
            "simulation_speed_seconds": self.simulation_speed_seconds,
            "postgres_host": self.postgres_host,
            "postgres_port": self.postgres_port,
            "postgres_db": self.postgres_db,
            "postgres_user": self.postgres_user,
            "postgres_password": "[MASKED]" if self.postgres_password else "[NOT_SET]",
            "log_level": self.log_level,
        }


def load_config() -> AppConfig:
    """
    Factory function to construct validated AppConfig from OS environment and .env.
    """
    return AppConfig(
        ingestion_mode=os.getenv("INGESTION_MODE", "fixture_replay"),
        allow_live_api=os.getenv("ALLOW_LIVE_API", "false").lower() in ("true", "1", "yes"),
        cricapi_key=os.getenv("CRICAPI_KEY", ""),
        cricapi_base_url=os.getenv("CRICAPI_BASE_URL", "https://api.cricapi.com/v1"),
        api_daily_quota_limit=int(os.getenv("API_DAILY_QUOTA_LIMIT", "100")),
        api_safety_margin_hits=int(os.getenv("API_SAFETY_MARGIN_HITS", "10")),
        api_poll_interval_seconds=int(os.getenv("API_POLL_INTERVAL_SECONDS", "120")),
        simulation_speed_seconds=int(os.getenv("SIMULATION_SPEED_SECONDS", "30")),
        target_match_id=os.getenv("TARGET_MATCH_ID", ""),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "godrej_cricket_db"),
        postgres_user=os.getenv("POSTGRES_USER", "postgres"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file_path=os.getenv("LOG_FILE_PATH", "logs/ingestion.log"),
    )
