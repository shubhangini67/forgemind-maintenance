from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = ROOT_DIR / "data"
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SteelPlant Maintenance Wizard"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "dev-secret-key"
    api_prefix: str = "/api/v1"

    data_dir: str = str(DEFAULT_DATA_DIR)

    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DATA_DIR / 'spmw.db'}"
    database_url_sync: str = f"sqlite:///{DEFAULT_DATA_DIR / 'spmw.db'}"

    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "maintenance_knowledge"
    vector_store_mode: Literal["auto", "local", "qdrant"] = "auto"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    llm_provider: Literal["gemini", "groq", "ollama", "rule_based"] = "rule_based"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    jwt_secret_key: str = "dev-jwt-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Re-index operational RAG on every startup (slow). Default off — enable for first deploy or manual refresh.
    bootstrap_rag_index: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_async_database_url(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("database_url_sync", mode="before")
    @classmethod
    def normalize_sync_database_url(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql+asyncpg://"):
            return value.replace("postgresql+asyncpg://", "postgresql://", 1)
        return value

    @property
    def resolved_data_dir(self) -> Path:
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def local_vector_path(self) -> Path:
        return self.resolved_data_dir / "vector_store.json"

    @property
    def models_dir(self) -> Path:
        path = ROOT_DIR / "backend" / "models"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def effective_llm_provider(self) -> str:
        if self.llm_provider == "groq" and self.groq_api_key:
            return "groq"
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            if self.groq_api_key:
                return "groq"
            return "rule_based"
        if self.llm_provider == "gemini" and self.gemini_api_key:
            return "gemini"
        return self.llm_provider

    @property
    def deploy_summary(self) -> dict:
        return {
            "database": "postgres" if self.is_postgres else "sqlite",
            "vector_store": self.vector_store_mode,
            "llm_provider": self.effective_llm_provider,
            "gemini_configured": bool(self.gemini_api_key),
            "groq_configured": bool(self.groq_api_key),
            "environment": self.app_env,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
