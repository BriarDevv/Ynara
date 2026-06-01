"""Settings de la aplicación cargados desde variables de entorno.

Pydantic Settings v2 con .env como fuente. Cualquier variable nueva
se agrega acá + en ``apps/backend/.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
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

    # Embeddings (ADR-008: bge-m3 1024-dim on-prem). `embedding_backend` elige
    # entre el Fake determinista (default, sin GPU) y el cliente vLLM real
    # (cuando el servidor de embeddings esté levantado, ADR-009).
    embedding_model: str = Field("bge-m3", alias="EMBEDDING_MODEL")
    embedding_base_url: str = Field("http://localhost:8003/v1", alias="EMBEDDING_BASE_URL")
    embedding_backend: Literal["fake", "vllm"] = Field("fake", alias="EMBEDDING_BACKEND")

    # Cifrado de memoria a nivel campo (ADR-007 D3). Base64 de 32 bytes random
    # (`openssl rand -base64 32`). Vacío => el helper de crypto falla al primer
    # uso (no se importa la key al boot). NUNCA commitear (regla #2).
    memory_encryption_master_key: str = Field("", alias="MEMORY_ENCRYPTION_MASTER_KEY")

    # Auth
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(10080, alias="JWT_EXPIRE_MINUTES")
    # TTL del refresh token. Mayor que el access (30 dias por default). Se usa
    # el MISMO secret/alg que el access; el claim `type` separa los dominios.
    jwt_refresh_expire_minutes: int = Field(43200, alias="JWT_REFRESH_EXPIRE_MINUTES")
    # Reuse-detection de refresh a nivel familia (sid), retry-safe (item 1 de #142).
    # Ventana de gracia tras rotar un refresh: dentro de ella, un reenvio del MISMO
    # refresh (retry de red benigno, comun en mobile que perdio la respuesta) NO
    # revoca la familia — se trata como reintento idempotente. Fuera de la ventana,
    # un refresh ya rotado que resurge es replay/robo -> revoca la familia entera.
    auth_refresh_reuse_grace_seconds: int = Field(30, alias="AUTH_REFRESH_REUSE_GRACE_SECONDS")

    # Rate-limit / lockout del login (issue #63). Bucket por (ip, email_hash).
    # El estado vive solo en Redis (sin tablas). fail-OPEN: si Redis cae, el
    # login procede sin freno (baseline pre-#63), nunca se auto-DoSea.
    auth_login_max_attempts: int = Field(5, alias="AUTH_LOGIN_MAX_ATTEMPTS")
    auth_login_window_seconds: int = Field(900, alias="AUTH_LOGIN_WINDOW_SECONDS")
    auth_login_lockout_seconds: int = Field(900, alias="AUTH_LOGIN_LOCKOUT_SECONDS")
    # Rate-limit del register, por IP (el email aun no existe). Mas laxo.
    auth_register_max_attempts: int = Field(10, alias="AUTH_REGISTER_MAX_ATTEMPTS")
    auth_register_window_seconds: int = Field(3600, alias="AUTH_REGISTER_WINDOW_SECONDS")

    # Storage (R2)
    r2_account_id: str = Field("", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field("", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field("", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field("ynara-uploads", alias="R2_BUCKET")

    # Observabilidad
    sentry_dsn: str = Field("", alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(0.0, ge=0.0, le=1.0, alias="SENTRY_TRACES_SAMPLE_RATE")
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

    @model_validator(mode="after")
    def _reject_weak_jwt_secret_in_prod(self) -> Settings:
        """Fail-fast: en production el JWT_SECRET no puede ser débil ni placeholder.

        Un secret débil o conocido permite forjar tokens y suplantar a cualquier
        usuario. En development/staging se permite para no meter fricción.
        """
        if self.environment == "production":
            weak = {"", "cambiar-en-produccion", "secret", "changeme"}
            if self.jwt_secret in weak or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET débil o placeholder en production: mínimo 32 chars; "
                    "generar con `openssl rand -base64 48`"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
