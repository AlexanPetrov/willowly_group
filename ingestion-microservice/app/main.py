"""FastAPI application for ingestion microservice with JWT authentication."""

import os
import tempfile
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from app.logger import logger
from app.schemas import IngestResponse, StatusResponse, HealthCheckResponse
from app.auth import decode_access_token
from app.tasks import ingest_document_task, celery_app

# ==================== FastAPI Setup ====================

app = FastAPI(
    title="Ingestion Microservice",
    description="Async document ingestion with JWT auth and Celery background processing",
    version="0.1.0",
)

auth_scheme = HTTPBearer(auto_error=True)


# ==================== Dependency: Extract User from JWT ====================

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> str:
    """Validate JWT token and extract user ID from 'sub' claim."""
    try:
        token = creds.credentials
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )
        return user_id
    except ValueError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        ) from e


# ==================== Routes ====================

@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.APP_ENV,
    )


@app.post("/v1/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
) -> IngestResponse:
    """
    Upload and queue a document for ingestion.
    
    Accepts PDF or TXT files and queues them for background processing via Celery.
    Returns immediately with a task ID for tracking progress.
    
    **Authentication**: Required (Bearer token from User Service)
    
    **Returns**:
    - task_id: Use this to check ingestion status
    - status: Always "processing" for successful requests
    - message: Confirmation message
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower().lstrip(".")
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file_ext}. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # Validate file size
    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )
    
    try:
        # Save file to temporary location
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(
            dir=settings.UPLOAD_DIR,
            delete=False,
            suffix=f".{file_ext}"
        ) as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            temp_path = tmp_file.name
        
        logger.info(
            "File uploaded by user %s: %s (temp: %s)",
            user_id,
            file.filename,
            temp_path
        )
        
        # Queue Celery task
        task = ingest_document_task.delay(
            file_path=temp_path,
            user_id=user_id,
            filename=file.filename
        )
        
        logger.info(
            "Ingestion task queued for user %s: %s (task_id: %s)",
            user_id,
            file.filename,
            task.id
        )
        
        return IngestResponse(
            task_id=task.id,
            status="processing",
            message=f"Document '{file.filename}' queued for processing"
        )
        
    except Exception as e:
        logger.error("Failed to queue ingestion task: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue ingestion task"
        ) from e


@app.get("/v1/ingest/status/{task_id}", response_model=StatusResponse)
async def ingest_status(
    task_id: str,
    user_id: str = Depends(get_current_user),
) -> StatusResponse:
    """
    Check the status of an ingestion task.
    
    **Parameters**:
    - task_id: The task ID returned from /v1/ingest
    
    **Returns**:
    - status: "processing", "completed", or "failed"
    - result: Ingestion stats when completed
    
    **Authentication**: Required (Bearer token)
    """
    task = celery_app.AsyncResult(task_id)
    
    logger.debug("Status check for task %s by user %s", task_id, user_id)
    
    if task.state == "PENDING":
        return StatusResponse(
            task_id=task_id,
            status="processing",
            message="Task is queued and waiting to be processed",
            result=None
        )
    
    elif task.state == "PROGRESS":
        return StatusResponse(
            task_id=task_id,
            status="processing",
            message="Task is being processed",
            result=task.info if isinstance(task.info, dict) else None
        )
    
    elif task.state == "SUCCESS":
        return StatusResponse(
            task_id=task_id,
            status="completed",
            message="Ingestion completed successfully",
            result=task.result
        )
    
    elif task.state == "FAILURE":
        error_msg = str(task.info) if task.info else "Unknown error"
        logger.warning("Task %s failed: %s", task_id, error_msg)
        return StatusResponse(
            task_id=task_id,
            status="failed",
            message=f"Ingestion failed: {error_msg}",
            result=None
        )
    
    else:
        return StatusResponse(
            task_id=task_id,
            status=task.state.lower(),
            message=f"Task state: {task.state}",
            result=None
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
