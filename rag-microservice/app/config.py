"""Configuration management for RAG Microservice using Pydantic Settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env files."""

    @staticmethod
    def get_env_file() -> str | None:
        """Mirror user-microservice pattern for env file discovery, with .env fallback."""
        if os.getenv("SKIP_ENV_FILE"):
            return None
        env = os.getenv("APP_ENV", "dev")
        env_file = f".env.{env}"
        if os.path.exists(env_file):
            return env_file
        # Fallback to .env if present
        return ".env" if os.path.exists(".env") else None

    model_config = SettingsConfigDict(
        env_file=get_env_file.__func__(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==================== Application ====================
    APP_NAME: str = "RAG Microservice"
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_METRICS: bool = True

    # ==================== CORS ====================
    CORS_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )

    # ==================== Models (LLM & Embeddings) ====================
    GEN_MODEL: str = os.getenv("GEN_MODEL", "llama3.1:8b")
    NUM_CTX: int = int(os.getenv("NUM_CTX", "4096"))
    NUM_PREDICT: int = int(os.getenv("NUM_PREDICT", "512"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.25"))

    # ==================== Vector DB ====================
    CHROMA_PATH: Path = Path(os.getenv("CHROMA_PATH", "../data/chroma_db")).resolve()
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "rag_docs")
    CHROMA_DISTANCE: str = os.getenv("CHROMA_DISTANCE", "cosine")

    # ==================== Retrieval ====================
    RETRIEVAL_K: int = int(os.getenv("RETRIEVAL_K", "2"))
    MIN_SIMILARITY: float = float(os.getenv("MIN_SIMILARITY", "0.65"))

    # ==================== Security (JWT) ====================
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

    # ==================== Ollama ====================
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

    # ==================== Shutdown ====================
    GRACEFUL_SHUTDOWN_TIMEOUT: int = int(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT", "30"))

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if not v:
            raise ValueError("SECRET_KEY (JWT secret) is required for RAG auth")
        if len(v) < 16:
            raise ValueError("SECRET_KEY must be sufficiently long")
        return v

    def get_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
