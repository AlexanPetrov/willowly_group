"""Configuration management for Ingestion Service using Pydantic."""

from pathlib import Path
from pydantic import Field, field_validator  # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables or .env files.
    
    Validates all settings on instantiation.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )
    
    # ==================== Application Settings ====================
    APP_NAME: str = Field(default="Ingestion Microservice", description="Application name")
    APP_ENV: str = Field(default="dev", description="Environment: dev, test, prod")
    
    # ==================== Paths ====================
    RAW_DATA_DIR: Path = Field(
        default=Path("../data/raw"),
        description="Root directory for raw documents"
    )
    CHROMA_PATH: Path = Field(
        default=Path("../data/chroma_db"),
        description="ChromaDB vector store path"
    )
    
    # ==================== ChromaDB ====================
    CHROMA_COLLECTION_NAME: str = Field(
        default="rag_docs",
        description="ChromaDB collection name"
    )
    CHROMA_DISTANCE: str = Field(
        default="cosine",
        description="Distance metric: cosine, l2, ip"
    )
    
    # ==================== Embedding Model ====================
    EMB_MODEL: str = Field(
        default="nomic-embed-text",
        description="Ollama embedding model name"
    )
    OLLAMA_HOST: str = Field(
        default="http://127.0.0.1:11434",
        description="Ollama API endpoint"
    )
    
    # ==================== Chunking ====================
    CHARS_PER_TOKEN: float = Field(
        default=4.0,
        gt=0,
        description="Average characters per token for chunk size calculation"
    )
    CHUNK_TOKENS: int = Field(
        default=800,
        gt=0,
        description="Target chunk size in tokens"
    )
    CHUNK_OVERLAP_TOKENS: int = Field(
        default=140,
        ge=0,
        description="Overlap between chunks in tokens"
    )
    
    # ==================== Ingestion Pipeline ====================
    HASH_ALGO: str = Field(
        default="xxh3",
        description="Hash algorithm: xxh3, md5"
    )
    INGEST_BATCH_SIZE: int = Field(
        default=128,
        gt=0,
        description="Batch size for ChromaDB upserts"
    )
    MAX_WORKERS: int = Field(
        default=4,
        gt=0,
        description="Max concurrent workers"
    )
    EMBEDDING_TIMEOUT: int = Field(
        default=30,
        gt=0,
        description="Ollama embedding timeout in seconds"
    )
    EMBEDDING_RETRIES: int = Field(
        default=3,
        ge=0,
        description="Max retries for embedding requests"
    )
    
    # ==================== Memory Optimization ====================
    ADAPTIVE_BATCH_SIZE: bool = Field(
        default=True,
        description="Automatically adjust batch size based on chunk size"
    )
    STREAM_CHUNK_SIZE: int = Field(
        default=65536,
        gt=0,
        description="File read buffer size in bytes (64KB default)"
    )
    MEMORY_BUFFER_MB: int = Field(
        default=100,
        gt=0,
        description="Target memory buffer size in MB for batch processing"
    )
    
    # ==================== API & Authentication ====================
    API_HOST: str = Field(
        default="0.0.0.0",
        description="FastAPI server host"
    )
    API_PORT: int = Field(
        default=8003,
        description="FastAPI server port"
    )
    JWT_SECRET_KEY: str = Field(
        description="Secret key for JWT token signing (shared with User/RAG services, required from env)"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    
    @field_validator('JWT_SECRET_KEY')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate that JWT_SECRET_KEY is provided and sufficiently long."""
        if not v:
            raise ValueError("JWT_SECRET_KEY is required but not provided in environment variables")
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long for security")
        return v
    
    # ==================== Redis & Celery ====================
    REDIS_URL: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis URL for Celery broker"
    )
    CELERY_BROKER_URL: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Celery broker URL (usually same as REDIS_URL)"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://127.0.0.1:6379/1",
        description="Celery result backend URL"
    )
    
    # ==================== File Upload ====================
    UPLOAD_DIR: Path = Field(
        default=Path("../data/uploads"),
        description="Temporary directory for uploaded files"
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=100,
        description="Maximum upload file size in MB"
    )
    ALLOWED_EXTENSIONS: list[str] = Field(
        default=["pdf", "txt"],
        description="Allowed file extensions"
    )
    
    # ==================== Logging ====================
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR"
    )
    LOG_FILE: str | None = Field(
        default="ingestion.log",
        description="Log file path, or None to disable file logging"
    )
    LOG_FORMAT: str = Field(
        default="console",
        description="Log format: console or json"
    )
    
    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        """Validate APP_ENV is one of allowed values."""
        allowed = {"dev", "test", "prod"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}, got {v}")
        return v
    
    @field_validator("CHROMA_DISTANCE")
    @classmethod
    def validate_distance(cls, v: str) -> str:
        """Validate distance metric."""
        allowed = {"cosine", "l2", "ip"}
        if v not in allowed:
            raise ValueError(f"CHROMA_DISTANCE must be one of {allowed}, got {v}")
        return v
    
    @field_validator("HASH_ALGO")
    @classmethod
    def validate_hash_algo(cls, v: str) -> str:
        """Validate hash algorithm."""
        allowed = {"xxh3", "md5"}
        if v not in allowed:
            raise ValueError(f"HASH_ALGO must be one of {allowed}, got {v}")
        return v
    
    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        allowed = {"console", "json"}
        if v not in allowed:
            raise ValueError(f"LOG_FORMAT must be one of {allowed}, got {v}")
        return v
    
    @property
    def chunk_chars(self) -> int:
        """Calculate chunk size in characters."""
        return int(self.CHUNK_TOKENS * self.CHARS_PER_TOKEN)
    
    @property
    def chunk_overlap_chars(self) -> int:
        """Calculate chunk overlap in characters."""
        return int(self.CHUNK_OVERLAP_TOKENS * self.CHARS_PER_TOKEN)
    
    def get_raw_pdfs_dir(self) -> Path:
        """Get raw PDFs directory."""
        return self.RAW_DATA_DIR / "pdfs"
    
    def get_raw_txts_dir(self) -> Path:
        """Get raw TXTs directory."""
        return self.RAW_DATA_DIR / "txts"


settings = Settings()

