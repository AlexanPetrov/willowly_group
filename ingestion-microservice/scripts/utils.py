"""Shared utility functions for text processing during data ingestion."""

from pathlib import Path
import hashlib
import xxhash
from pypdf import PdfReader
from config import CHUNK_CHARS, CHUNK_OVERLAP_CHARS, HASH_ALGO


def hash_text(text: str) -> str:
    """Generates a unique cryptographic hash (MD5 or XXH3) of input text for deduplication."""
    
    data = text.encode("utf-8")
    if HASH_ALGO.lower() == "xxh3":
        return xxhash.xxh3_128_hexdigest(data) # XXH3 - fast algo. to generate a 128-bit hash & return its hex string
    return hashlib.md5(data).hexdigest() # cryptographically-secure MD5 - slow algorithm (fallback) to generate a hash & return its hex string

def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks of fixed size."""
    
    chunks: list[str] = []
    step = max(1, CHUNK_CHARS - CHUNK_OVERLAP_CHARS)
    for start in range(0, len(text), step):
        chunk = text[start : start + CHUNK_CHARS].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def stable_chunk_id(filename: str, idx: int, digest: str) -> str:
    """Create a stable chunk ID from filename, chunk index, and content hash."""
    
    return f"{filename}_{idx}_{digest}"

def extract_text_from_pdf(pdf_path: Path | str) -> str | None:
    """Extract raw text from a PDF, or None if nothing could be read."""
    
    try:
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            parts: list[str] = []
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    parts.append(txt)
            return "\n".join(parts) if parts else None
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"PDF text extraction failed: {e}") from e
