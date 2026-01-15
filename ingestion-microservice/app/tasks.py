"""Celery tasks for background document ingestion."""

import os
import shutil
from pathlib import Path
from celery import Celery
from config import settings
from app.pipeline import run_ingestion_pipeline
from app.logger import logger

# Initialize Celery app
celery_app = Celery(
    __name__,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(bind=True, name="ingest_document")
def ingest_document_task(self, file_path: str, user_id: str, filename: str) -> dict:
    """Background task to ingest a document.
    
    Args:
        file_path: Path to the uploaded file (temporary location)
        user_id: User ID from JWT token
        filename: Original filename
        
    Returns:
        Result dictionary with ingestion stats
    """
    try:
        logger.info(
            "Starting ingestion task for user %s: %s (task_id: %s)",
            user_id,
            filename,
            self.request.id
        )
        
        # Move file to user-specific storage directory
        user_data_dir = settings.RAW_DATA_DIR / user_id
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine destination based on file extension
        file_ext = Path(filename).suffix.lower().lstrip(".")
        if file_ext == "pdf":
            dest_dir = user_data_dir / "pdfs"
        elif file_ext == "txt":
            dest_dir = user_data_dir / "txts"
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        
        # Move file from temp location to user storage
        shutil.move(file_path, str(dest_path))
        logger.debug("File moved to %s", dest_path)
        
        # Run ingestion pipeline
        result = run_ingestion_pipeline(
            raw_data_dir=user_data_dir,
            user_id=user_id
        )
        
        logger.info(
            "Ingestion completed for user %s: %s (task_id: %s)",
            user_id,
            filename,
            self.request.id
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "filename": filename,
            "file_path": str(dest_path),
            **result  # Unpack pipeline result stats
        }
        
    except Exception as e:
        logger.error(
            "Ingestion failed for user %s: %s (task_id: %s) - %s",
            user_id,
            filename,
            self.request.id,
            str(e),
            exc_info=True
        )
        # Clean up temp file if it still exists
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as cleanup_error:
            logger.warning("Failed to clean up temp file %s: %s", file_path, cleanup_error)
        
        raise
