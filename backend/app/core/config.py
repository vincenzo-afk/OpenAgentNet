from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://openagentnet:openagentnet@localhost:5432/openagentnet"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # NATS
    nats_url: str = "nats://localhost:4222"

    # JWT
    jwt_private_key_path: str = "keys/jwt_private.pem"
    jwt_public_key_path: str = "keys/jwt_public.pem"
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # API
    api_v1_prefix: str = "/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Trust score weights
    trust_weight_outcome: float = 0.40
    trust_weight_latency: float = 0.25
    trust_weight_dispute: float = 0.25
    trust_weight_age: float = 0.10

    # Rate limits (per minute)
    rate_limit_register: int = 10
    rate_limit_discover: int = 200
    rate_limit_messages: int = 1000
    rate_limit_endorse: int = 50

    # Agent heartbeat
    heartbeat_interval_seconds: int = 60
    heartbeat_miss_threshold: int = 3

    # Payload limits
    max_payload_bytes: int = 1_048_576  # 1MB

    @property
    def jwt_private_key(self) -> str:
        return Path(self.jwt_private_key_path).read_text()

    @property
    def jwt_public_key(self) -> str:
        return Path(self.jwt_public_key_path).read_text()


@lru_cache
def get_settings() -> Settings:
    return Settings()
