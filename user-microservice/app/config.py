# LOADS & VALIDATES ENV VARS from environment-specific .env file

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    # Determine which .env file to load based on APP_ENV environment variable
    # Default to "dev" if not set
    # Skip file loading if SKIP_ENV_FILE is set (e.g., in Docker with env vars)
    @staticmethod
    def get_env_file() -> str | None:
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
        env_file=get_env_file.__func__(),  # Load environment-specific file (or None for Docker)
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Application settings
    APP_NAME: str = "User Microservice"
    APP_ENV: str = "dev"
    DB_URL: str  # Required - will raise error if missing
    
    # Database connection pool settings
    DB_POOL_SIZE: int = 20  # Number of connections to maintain in pool
    DB_MAX_OVERFLOW: int = 10  # Max connections beyond pool_size
    DB_POOL_TIMEOUT: int = 30  # Seconds to wait for connection from pool
    DB_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour
    
    # Database resilience settings
    DB_RETRY_MAX_ATTEMPTS: int = 3  # Maximum retry attempts for failed queries
    DB_RETRY_BASE_DELAY: float = 0.5  # Base delay for exponential backoff (seconds)
    DB_QUERY_TIMEOUT: int = 60  # Query execution timeout (seconds)
    DB_CONNECT_TIMEOUT: int = 10  # Connection timeout (seconds)
    
    # CORS settings
    CORS_ORIGINS: str = "http://localhost:3000"  # Comma-separated list of allowed origins
    
    # Pagination defaults
    DEFAULT_PAGE: int = 1
    DEFAULT_LIMIT: int = 10
    MAX_LIMIT: int = 100
    
    # Batch & Chunk operation limits
    MAX_BATCH_SIZE: int = 1000
    CHUNK_SIZE: int = 100
    
    # Field validation constraints
    USER_NAME_MAX_LENGTH: int = 100
    USER_EMAIL_MAX_LENGTH: int = 255
    
    # JWT Authentication
    JWT_SECRET_KEY: str  # Required - will raise error if missing
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 30
    
    # Rate limiting (requests per minute)
    RATE_LIMIT_BATCH: str = "10/minute"
    RATE_LIMIT_WRITE: str = "60/minute"
    RATE_LIMIT_READ: str = "100/minute"
    
    # Graceful shutdown settings
    GRACEFUL_SHUTDOWN_TIMEOUT: int = 30  # Max seconds to wait for active requests to complete
    
    # Logging settings
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FILE: str | None = "app.log"  # Set to None to disable file logging
    LOG_FORMAT: str = "console"  # "console" for dev, "json" for production
    
    # Redis cache settings
    REDIS_URL: str = "redis://localhost:6379/0"  # Redis connection string
    CACHE_TTL: int = 300  # Default cache TTL in seconds (5 minutes)
    CACHE_ENABLED: bool = True  # Enable/disable caching globally
    
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
