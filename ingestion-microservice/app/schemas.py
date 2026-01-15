"""Request and response schemas for ingestion API."""

from pydantic import BaseModel, ConfigDict, Field


class IngestResponse(BaseModel):
    """Response body for successful ingestion request."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "abc123def456",
                "status": "processing",
                "message": "Document queued for processing"
            }
        }
    )
    
    task_id: str = Field(description="Celery task ID for tracking")
    status: str = Field(default="processing", description="Current status")
    message: str = Field(description="Human-readable message")


class StatusResponse(BaseModel):
    """Response body for ingestion status check."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "abc123def456",
                "status": "completed",
                "message": "Ingestion completed",
                "result": {
                    "files_processed": 1,
                    "chunks_total": 5,
                    "chunks_added": 5,
                    "chunks_skipped": 0,
                    "elapsed_seconds": 2.5
                }
            }
        }
    )
    
    task_id: str = Field(description="Celery task ID")
    status: str = Field(description="Current status: processing, completed, failed")
    message: str = Field(description="Status message")
    result: dict | None = Field(default=None, description="Result data when completed")


class HealthCheckResponse(BaseModel):
    """Response body for health check endpoint."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "environment": "dev"
            }
        }
    )
    
    status: str = Field(description="Service status")
    version: str = Field(description="Service version")
    environment: str = Field(description="Environment: dev, test, prod")
