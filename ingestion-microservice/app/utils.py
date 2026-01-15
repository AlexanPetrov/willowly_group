"""Async text processing utilities for ingestion pipeline."""

from pathlib import Path
import hashlib
import xxhash  # type: ignore
import aiofiles  # type: ignore
from pypdf import PdfReader  # type: ignore
from typing import AsyncIterator
from config import settings
from app.logger import logger


def hash_text(text: str) -> str:
    """Generates a unique cryptographic hash (MD5 or XXH3) of input text for deduplication."""
    data = text.encode("utf-8")
    if settings.HASH_ALGO.lower() == "xxh3":
        return xxhash.xxh3_128_hexdigest(data)
    return hashlib.md5(data).hexdigest()


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks of fixed size."""
    chunks: list[str] = []
    step = max(1, settings.chunk_chars - settings.chunk_overlap_chars)
    
    for start in range(0, len(text), step):
        chunk = text[start : start + settings.chunk_chars].strip()
        if chunk:
            chunks.append(chunk)
    
    return chunks


async def stream_chunks(text: str) -> AsyncIterator[str]:
    """Asynchronously stream text chunks to avoid loading all into memory.
    
    Yields chunks one at a time for memory-efficient processing.
    
    Args:
        text: Full text to chunk
        
    Yields:
        Individual chunks
    """
    step = max(1, settings.chunk_chars - settings.chunk_overlap_chars)
    
    for start in range(0, len(text), step):
        chunk = text[start : start + settings.chunk_chars].strip()
        if chunk:
            yield chunk


def stable_chunk_id(filename: str, idx: int, digest: str) -> str:
    """Create a stable chunk ID from filename, chunk index, and content hash."""
    return f"{filename}_{idx}_{digest}"


async def extract_text_from_pdf(pdf_path: Path | str) -> str | None:
    """Extract raw text from a PDF asynchronously.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text or None if nothing could be read
        
    Raises:
        FileNotFoundError: If PDF file not found
        ValueError: If PDF text extraction failed
    """
    pdf_path = Path(pdf_path)
    
    try:
        # PDF processing is CPU-bound, do synchronously
        reader = PdfReader(pdf_path)
        parts: list[str] = []
        
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                parts.append(txt)
        
        return "\n".join(parts) if parts else None
        
    except FileNotFoundError:
        logger.error(f"PDF file not found: {pdf_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to extract text from PDF '{pdf_path}': {e}")
        raise ValueError(f"PDF text extraction failed: {e}") from e


async def extract_text_from_txt(txt_path: Path | str) -> str | None:
    """Extract text from a plain text file asynchronously.
    
    Args:
        txt_path: Path to text file
        
    Returns:
        File content or None if empty
        
    Raises:
        FileNotFoundError: If text file not found
    """
    txt_path = Path(txt_path)
    
    try:
        async with aiofiles.open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            text = await f.read()
        
        return text if text.strip() else None
        
    except FileNotFoundError:
        logger.error(f"Text file not found: {txt_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to read text file '{txt_path}': {e}")
        raise


async def stream_txt_lines(
    txt_path: Path | str,
    chunk_size: int = 65536,
) -> AsyncIterator[str]:
    """Stream lines from a text file in chunks to avoid loading large files into memory.
    
    Args:
        txt_path: Path to text file
        chunk_size: Read size in bytes per iteration (default 64KB)
        
    Yields:
        Lines from the file, preserving structure
    """
    txt_path = Path(txt_path)
    buffer = ""
    
    try:
        async with aiofiles.open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    if buffer:
                        yield buffer
                    break
                
                buffer += chunk
                lines = buffer.split("\n")
                
                # Yield all complete lines
                for line in lines[:-1]:
                    yield line + "\n"
                
                # Keep the last incomplete line in buffer
                buffer = lines[-1]
    
    except FileNotFoundError:
        logger.error(f"Text file not found: {txt_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to stream text file '{txt_path}': {e}")
        raise

