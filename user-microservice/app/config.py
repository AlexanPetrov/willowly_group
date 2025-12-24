"""Configuration management and validation using Pydantic."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables or .env files."""
    
    @staticmethod
    def get_env_file() -> str | None:
        """Determine which .env file to load based on environment variables.
        
        Returns:
            None if SKIP_ENV_FILE is set (Docker/direct env vars)
            .env.{APP_ENV} file path otherwise (defaults to .env.dev)
        """
        if os.getenv("SKIP_ENV_FILE"):
            return None
        env = os.getenv("APP_ENV", "dev")
        env_file = f".env.{env}"
        if not os.path.exists(env_file):
            raise FileNotFoundError(
                f"Environment file '{env_file}' not found. "
                f"Create it or set APP_ENV to 'dev' or 'prod'."
            )
        return env_file
    
    model_config = SettingsConfigDict(
        env_file=get_env_file.__func__(),
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # ==================== Application Settings ====================
    APP_NAME: str = "User Microservice"
    APP_ENV: str = "dev"
    DB_URL: str  # Required, defined in .env files
    
    # ==================== Database Connection Pooling ====================
    DB_POOL_SIZE: int = 20  # Persistent connections in pool
    DB_MAX_OVERFLOW: int = 10  # Additional connections beyond pool size
    DB_POOL_TIMEOUT: int = 30  # Seconds to wait for available connection
    DB_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour
    
    # ==================== Database Resilience ====================
    DB_RETRY_MAX_ATTEMPTS: int = 3  # Max retry attempts for failed queries
    DB_RETRY_BASE_DELAY: float = 0.5  # Base delay for exponential backoff (seconds)
    DB_QUERY_TIMEOUT: int = 60  # Query execution timeout (seconds)
    DB_CONNECT_TIMEOUT: int = 10  # Connection establishment timeout (seconds)
    
    # ==================== CORS Settings ====================
    CORS_ORIGINS: str = "http://localhost:3000"  # Comma-separated allowed origins
    
    # ==================== Pagination ====================
    DEFAULT_PAGE: int = 1
    DEFAULT_LIMIT: int = 10
    MAX_LIMIT: int = 100
    
    # ==================== Batch Operations ====================
    MAX_BATCH_SIZE: int = 1000
    CHUNK_SIZE: int = 100
    
    # ==================== Field Validation ====================
    USER_NAME_MAX_LENGTH: int = 100
    USER_EMAIL_MAX_LENGTH: int = 255
    
    # ==================== JWT Authentication ====================
    JWT_SECRET_KEY: str  # Required, defined in .env files
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 30
    
    # ==================== Rate Limiting ====================
    RATE_LIMIT_BATCH: str = "10/minute"
    RATE_LIMIT_WRITE: str = "60/minute"
    RATE_LIMIT_READ: str = "100/minute"
    
    # ==================== Graceful Shutdown ====================
    GRACEFUL_SHUTDOWN_TIMEOUT: int = 30  # Max wait time for active requests (seconds)
    
    # ==================== Logging ====================
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FILE: str | None = "app.log"  # None to disable file logging
    LOG_FORMAT: str = "console"  # "console" for dev, "json" for production
    
    # ==================== Redis Caching ====================
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # Default TTL in seconds (5 minutes)
    CACHE_ENABLED: bool = True  # Global cache toggle
    
    @field_validator('DB_URL')
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        """Validate that DB_URL is provided and properly formatted."""
        if not v:
            raise ValueError("DB_URL is required but not provided in environment variables")
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DB_URL must be a valid PostgreSQL connection string")
        return v
    
    @field_validator('JWT_SECRET_KEY')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate that JWT_SECRET_KEY is provided and sufficiently long."""
        if not v:
            raise ValueError("JWT_SECRET_KEY is required but not provided in environment variables")
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long for security")
        return v
    
    def get_cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS into a list of allowed origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
