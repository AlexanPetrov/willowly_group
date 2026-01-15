"""Async data ingestion pipeline for processing documents into ChromaDB."""

import asyncio
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

from config import settings
from app.logger import logger
from app.utils import (
    extract_text_from_pdf,
    extract_text_from_txt,
    stream_chunks,
    hash_text,
    stable_chunk_id,
)
from app.chroma import chroma_client
from app.memory import MemoryMonitor, calculate_adaptive_batch_size


# ==================== Statistics ====================

@dataclass(slots=True)
class IngestionStats:
    """Statistics for ingestion pipeline execution."""
    files_processed: int = 0
    files_failed: int = 0
    total_chunks: int = 0
    chunks_added: int = 0
    chunks_skipped: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    
    @property
    def elapsed_seconds(self) -> float:
        """Total elapsed time in seconds."""
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()
    
    @property
    def chunks_per_second(self) -> float:
        """Processing throughput in chunks/sec."""
        elapsed = self.elapsed_seconds
        return self.total_chunks / elapsed if elapsed > 0 else 0
    
    def __str__(self) -> str:
        """Formatted statistics summary."""
        return (
            f"Files: {self.files_processed} ok, {self.files_failed} failed | "
            f"Chunks: {self.total_chunks} total, {self.chunks_added} added, {self.chunks_skipped} skipped | "
            f"Time: {self.elapsed_seconds:.2f}s ({self.chunks_per_second:.2f} chunks/sec)"
        )


# ==================== File Discovery ====================

async def iter_raw_texts() -> AsyncIterator[tuple[str, str]]:
    """Yield (filename, text) from RAW_PDFS / RAW_TXTS directories asynchronously.
    
    Skips files with errors and yields valid documents.
    
    Yields:
        Tuples of (filename, extracted_text)
    """
    pdfs_dir = settings.get_raw_pdfs_dir()
    txts_dir = settings.get_raw_txts_dir()
    
    # Create directories if they don't exist
    pdfs_dir.mkdir(parents=True, exist_ok=True)
    txts_dir.mkdir(parents=True, exist_ok=True)
    
    # Process PDFs
    for pdf_path in sorted(pdfs_dir.rglob("*.pdf")):
        try:
            logger.debug(f"Processing PDF: {pdf_path.name}")
            text = await extract_text_from_pdf(pdf_path)
            if text and text.strip():
                yield (pdf_path.name, text)
            else:
                logger.warning(f"PDF is empty: {pdf_path.name}")
        except FileNotFoundError:
            logger.warning(f"PDF file not found (skipping): {pdf_path.name}")
        except Exception as e:
            logger.error(f"Failed to process PDF '{pdf_path.name}': {e}")
    
    # Process text files
    for txt_path in sorted(txts_dir.rglob("*.txt")):
        try:
            logger.debug(f"Processing text file: {txt_path.name}")
            text = await extract_text_from_txt(txt_path)
            if text and text.strip():
                yield (txt_path.name, text)
            else:
                logger.warning(f"Text file is empty: {txt_path.name}")
        except FileNotFoundError:
            logger.warning(f"Text file not found (skipping): {txt_path.name}")
        except Exception as e:
            logger.error(f"Failed to process text file '{txt_path.name}': {e}")


# ==================== Ingestion Pipeline ====================

async def ingest(
    *,
    rebuild: bool = False,
    purge: bool = False,
    dry_run: bool = False,
    batch_size: int | None = None,
) -> IngestionStats:
    """Main async ingestion pipeline with memory optimization.
    
    Features:
    - Stream-based chunk processing (memory efficient)
    - Adaptive batch sizing based on chunk size
    - Memory monitoring and warnings
    - Incremental processing to avoid large in-memory buffers
    
    Args:
        rebuild: Delete collection before ingesting (idempotent mode)
        purge: Delete entire ChromaDB directory before ingesting
        dry_run: Don't actually store in ChromaDB (process only)
        batch_size: Documents to buffer before upserting (auto-calculated if None)
        
    Returns:
        IngestionStats with ingestion metrics
    """
    stats = IngestionStats()
    memory_monitor = MemoryMonitor()
    
    # Use provided batch size or use adaptive sizing
    if batch_size is None:
        batch_size = settings.INGEST_BATCH_SIZE
    
    logger.info(
        f"Starting ingestion pipeline "
        f"(rebuild={rebuild}, purge={purge}, dry_run={dry_run})"
    )
    logger.info(
        f"Batch size: {batch_size}, "
        f"Adaptive: {settings.ADAPTIVE_BATCH_SIZE}, "
        f"Model: {settings.EMB_MODEL}"
    )
    
    try:
        # ==================== Setup ====================
        
        # Purge entire database if requested
        if purge:
            if settings.CHROMA_PATH.exists():
                shutil.rmtree(settings.CHROMA_PATH, ignore_errors=True)
                logger.info(f"Purged ChromaDB at {settings.CHROMA_PATH}")
        
        # Connect to ChromaDB
        await chroma_client.connect()
        
        # Delete collection for rebuild
        await chroma_client.delete_collection(rebuild=rebuild)
        
        # ==================== Ingestion Loop ====================
        
        ids_buffer: list[str] = []
        docs_buffer: list[str] = []
        meta_buffer: list[dict] = []
        current_batch_size = batch_size
        adaptation_counter = 0
        
        async def flush_buffer() -> None:
            """Flush buffered documents to ChromaDB."""
            if not ids_buffer:
                return
            
            logger.debug(f"Flushing {len(ids_buffer)} buffered documents to ChromaDB")
            
            # Check for existing IDs (deduplication)
            existing = await chroma_client.check_existing_ids(ids_buffer)
            keep_indices = [i for i, id_ in enumerate(ids_buffer) if id_ not in existing]
            
            if keep_indices:
                new_ids = [ids_buffer[i] for i in keep_indices]
                new_docs = [docs_buffer[i] for i in keep_indices]
                new_metas = [meta_buffer[i] for i in keep_indices]
                
                if not dry_run:
                    # Upsert to ChromaDB (embeddings generated by ChromaDB's OllamaEmbeddingFunction)
                    await chroma_client.upsert_batch(new_ids, new_docs, new_metas)
                    stats.chunks_added += len(new_ids)
                    logger.debug(f"Added {len(new_ids)} new chunks")
                else:
                    logger.debug(f"[dry-run] Would add {len(new_ids)} chunks")
                    stats.chunks_added += len(new_ids)
            
            stats.chunks_skipped += len(existing)
            if existing:
                logger.debug(f"Skipped {len(existing)} duplicate chunks (already in DB)")
            
            # Clear buffers
            ids_buffer.clear()
            docs_buffer.clear()
            meta_buffer.clear()
            memory_monitor.reset()
        
        # Process documents
        async for filename, full_text in iter_raw_texts():
            stats.files_processed += 1
            logger.info(f"[{stats.files_processed}] Processing: {filename}")
            
            try:
                # Stream chunks for memory efficiency
                chunk_idx = 0
                async for chunk_text_content in stream_chunks(full_text):
                    stats.total_chunks += 1
                    
                    # Record memory usage
                    chunk_size = len(chunk_text_content.encode("utf-8"))
                    memory_monitor.record_chunk(chunk_size)
                    
                    # Adaptive batch sizing (adjust every 10 chunks)
                    if settings.ADAPTIVE_BATCH_SIZE and adaptation_counter % 10 == 0:
                        avg_size = memory_monitor.get_avg_chunk_size()
                        if avg_size > 0:
                            estimate = calculate_adaptive_batch_size(avg_size)
                            current_batch_size = estimate.batch_size
                            logger.debug(f"Adaptive batch size adjusted: {estimate}")
                    
                    adaptation_counter += 1
                    
                    chunk_hash = hash_text(chunk_text_content)
                    chunk_id = stable_chunk_id(Path(filename).stem, chunk_idx, chunk_hash)
                    
                    ids_buffer.append(chunk_id)
                    docs_buffer.append(chunk_text_content)
                    meta_buffer.append({
                        "source_file": filename,
                        "chunk_index": chunk_idx,
                        "chunk_hash": chunk_hash,
                    })
                    chunk_idx += 1
                    
                    # Flush when batch size reached
                    if len(ids_buffer) >= current_batch_size:
                        logger.debug(f"Batch full ({len(ids_buffer)}/{current_batch_size}), flushing")
                        await flush_buffer()
                
                logger.debug(f"  Processed {chunk_idx} chunks from {filename}")
            
            except Exception as e:
                logger.error(f"Failed to process file '{filename}': {e}")
                stats.files_failed += 1
        
        # Final flush
        await flush_buffer()
        
        stats.end_time = datetime.now(timezone.utc)
        logger.info(f"Ingestion complete: {stats}")
        logger.info(f"Memory stats: {memory_monitor}")
        
        return stats
    
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}", exc_info=True)
        stats.end_time = datetime.now(timezone.utc)
        raise

# ==================== CLI Wrapper ====================

async def main_async(
    rebuild: bool = False,
    purge: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Async main entry point for CLI.
    
    Args:
        rebuild: Delete collection before ingesting
        purge: Delete entire ChromaDB directory before ingesting
        dry_run: Process documents but don't store in ChromaDB
        verbose: Enable verbose logging output
    """
    try:
        stats = await ingest(rebuild=rebuild, purge=purge, dry_run=dry_run)
        
        # Log detailed stats in verbose mode
        if verbose:
            logger.info(f"Detailed Stats: Files={stats.files_processed}, "
                       f"Chunks={stats.total_chunks}, "
                       f"Added={stats.chunks_added}, "
                       f"Skipped={stats.chunks_skipped}, "
                       f"Failed={stats.files_failed}, "
                       f"Throughput={stats.chunks_per_second:.2f} chunks/s")
        
        logger.info(f"SUCCESS: {stats}")
    except Exception as e:
        logger.error(f"FAILED: {e}")
        raise


def main(
    rebuild: bool = False,
    purge: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Synchronous wrapper to run async pipeline from CLI."""
    asyncio.run(main_async(rebuild=rebuild, purge=purge, dry_run=dry_run, verbose=verbose))


def run_ingestion_pipeline(
    raw_data_dir: Path | str | None = None,
    user_id: str | None = None,
    rebuild: bool = False,
    purge: bool = False,
    dry_run: bool = False,
) -> dict:
    """Synchronous wrapper for API/Celery tasks to run ingestion with custom data dir.
    
    Args:
        raw_data_dir: Custom raw data directory (overrides config)
        user_id: User ID for logging
        rebuild: Delete collection before ingesting
        purge: Delete entire ChromaDB before ingesting
        dry_run: Process but don't store
        
    Returns:
        Dictionary with ingestion stats
    """
    # Temporarily override settings if custom raw_data_dir provided
    original_raw_dir = settings.RAW_DATA_DIR
    
    try:
        if raw_data_dir:
            settings.RAW_DATA_DIR = Path(raw_data_dir)
        
        stats = asyncio.run(
            ingest(rebuild=rebuild, purge=purge, dry_run=dry_run)
        )
        
        logger.info(
            f"Ingestion completed for user {user_id}: {stats}"
        )
        
        return {
            "files_processed": stats.files_processed,
            "files_failed": stats.files_failed,
            "chunks_total": stats.total_chunks,
            "chunks_added": stats.chunks_added,
            "chunks_skipped": stats.chunks_skipped,
            "elapsed_seconds": stats.elapsed_seconds,
            "throughput_chunks_per_sec": stats.chunks_per_second,
        }
    finally:
        # Restore original settings
        settings.RAW_DATA_DIR = original_raw_dir
