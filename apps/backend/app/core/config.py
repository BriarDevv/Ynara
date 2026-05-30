"""Settings de la aplicación cargados desde variables de entorno.

Pydantic Settings v2 con .env como fuente. Cualquier variable nueva
se agrega acá + en ``apps/backend/.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"

    # Database (Supabase en MVP, self-hosted en V2 — solo cambia el valor)
    database_url: str = Field(..., alias="DATABASE_URL")
    database_pool_size: int = Field(10, alias="DATABASE_POOL_SIZE")

    # Redis / Celery
    redis_url: str = Field(..., alias="REDIS_URL")
    celery_broker_url: str = Field("", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field("", alias="CELERY_RESULT_BACKEND")

    # LLM serving (ADR-009 D4): los base_url + topologia viven en settings;
    # served_name, parsers y quantization viven en ynara.config.json.
    llm_primary_base_url: str = Field("http://localhost:8001/v1", alias="LLM_PRIMARY_BASE_URL")
    llm_secondary_base_url: str = Field("http://localhost:8002/v1", alias="LLM_SECONDARY_BASE_URL")
    llm_topology: Literal["split_process", "single_process", "swap_lru"] = Field(
        "split_process", alias="LLM_TOPOLOGY"
    )

    # Embeddings
    embedding_model: str = Field("bge-m3", alias="EMBEDDING_MODEL")

    # Auth
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(10080, alias="JWT_EXPIRE_MINUTES")

    # Storage (R2)
    r2_account_id: str = Field("", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field("", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field("", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field("ynara-uploads", alias="R2_BUCKET")

    # Observabilidad
    sentry_dsn: str = Field("", alias="SENTRY_DSN")
    posthog_key: str = Field("", alias="POSTHOG_KEY")

    # CORS — TODO: ajustar a dominios reales al desplegar
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8081",
        ]
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Fallback: si Celery URLs no se setean, usar la de Redis
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis_url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
