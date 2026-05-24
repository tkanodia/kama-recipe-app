import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    cors_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
        description="Comma-separated list of allowed origins",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://kama:kama_local@127.0.0.1:5432/kama",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")

    clerk_jwks_url: str | None = Field(default=None, alias="CLERK_JWKS_URL")
    clerk_issuer: str | None = Field(default=None, alias="CLERK_ISSUER")
    disable_auth: bool = Field(default=False, alias="DISABLE_AUTH")

    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket: str | None = Field(default=None, alias="S3_BUCKET")
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")

    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")

    # LLM provider configuration — switch between openai and anthropic
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    qdrant_url: str = Field(default="http://127.0.0.1:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    admin_user_ids: str = Field(default="", alias="ADMIN_USER_IDS")

    google_application_credentials: str | None = Field(default=None, alias="GOOGLE_APPLICATION_CREDENTIALS")
    google_credentials_json: str | None = Field(
        default=None,
        alias="GOOGLE_CREDENTIALS_JSON",
        description="Inline GCP service account JSON for Cloud Vision (Railway/production)",
    )

    @property
    def resolved_database_url(self) -> str:
        """Normalize Railway/Heroku-style URLs for SQLAlchemy asyncpg."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def database_is_local(self) -> bool:
        lower = self.database_url.lower()
        return "localhost" in lower or "127.0.0.1" in lower

    @property
    def asyncpg_connect_args(self) -> dict:
        """Railway/managed Postgres requires SSL; local docker does not."""
        if self.database_is_local:
            return {}
        return {"ssl": True}

    @property
    def alembic_database_url(self) -> str:
        """Sync psycopg URL for Alembic migrations."""
        url = self.resolved_database_url
        sync = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if self.database_is_local or "sslmode=" in sync:
            return sync
        sep = "&" if "?" in sync else "?"
        return f"{sync}{sep}sslmode=require"

    @property
    def resolved_google_credentials_path(self) -> str | None:
        """Path to GCP credentials file, writing inline JSON to disk when configured."""
        if self.google_application_credentials:
            creds = self.google_application_credentials
            if not os.path.isabs(creds):
                creds = str(Path(__file__).resolve().parent.parent.parent / creds)
            return creds
        if self.google_credentials_json:
            path = Path("/tmp/kama-gcp-credentials.json")
            if not path.exists() or path.read_text() != self.google_credentials_json:
                path.write_text(self.google_credentials_json)
            return str(path)
        return None

    @property
    def resolved_llm_model(self) -> str:
        """Return the model slug to use, applying sensible defaults per provider."""
        if self.llm_model:
            return self.llm_model
        return {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
        }.get(self.llm_provider, "gpt-4o-mini")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_user_id_list(self) -> list[str]:
        return [u.strip() for u in self.admin_user_ids.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    creds_path = settings.resolved_google_credentials_path
    if creds_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    return settings
