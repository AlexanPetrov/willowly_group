# Pydantic schemas for request/response validation

from pydantic import BaseModel, Field
from typing import Literal
from app.config import settings


class QueryRequest(BaseModel):
    """Request schema for RAG query endpoint."""
    text: str = Field(..., description="User query text.")
    k: int = Field(
        default=settings.RETRIEVAL_K,
        ge=1,
        le=20,
        description="Top-K documents to retrieve (1–20).",
    )
    min_similarity: float = Field(
        default=settings.MIN_SIMILARITY,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold (0.0–1.0).",
    )
    max_tokens: int = Field(
        default=settings.NUM_PREDICT,
        ge=1,
        le=2048,
        description="Max tokens to generate (1–2048).",
    )
    stream: bool = Field(False, description="Concatenate streamed chunks into the response.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "What are lions?",
                "k": settings.RETRIEVAL_K,
                "min_similarity": settings.MIN_SIMILARITY,
                "max_tokens": settings.NUM_PREDICT,
                "stream": False,
            }
        }
    }

class DocumentMetadata(BaseModel):
    """Metadata for a retrieved document."""
    file: str | None = None
    source_path: str | None = None
    extra: dict = Field(default_factory=dict, description="Additional metadata fields.")

class QueryResponse(BaseModel):
    """Response schema for RAG query endpoint with retrieval and generation results."""
    response: str = Field(..., description="Generated answer from the LLM.")
    context_docs: list[str] = Field(..., description="Retrieved document chunks used for generation.")
    similarities: list[float] = Field(..., description="Similarity scores for retrieved documents.")
    metadata: list[DocumentMetadata] = Field(default_factory=list, description="Metadata for each retrieved document.")
    retrieval_stats: dict = Field(
        default_factory=dict,
        description="Retrieval statistics: retrieved_count, filtered_count, top_similarity."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Lions are apex predators native to Africa's savannas.",
                "context_docs": [
                    "Lions are apex predators native to Africa's savannas...",
                    "Prides consist of related females and their cubs..."
                ],
                "similarities": [0.78, 0.54],
            }
        }
    }

class HealthCheckResponse(BaseModel):
    """Health check response with service status and configuration details."""
    status: Literal["healthy", "degraded"]
    models: dict[str, str]
    ctx: dict[str, int]
    retrieval: dict[str, str | int | float]
    error: str | None = None
