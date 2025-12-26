"""
    Pipeline:
        1. Extract text from PDFs/TXTs
        2. Split it into chunks
        3. Hash chunks (for stable IDs / deduplication)
        4. Upsert into ChromaDB collection (idempotent)
"""

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator
import time
import argparse
import shutil
import logging

import chromadb
from chromadb.utils import embedding_functions

from scripts.utils import extract_text_from_pdf, chunk_text, hash_text, stable_chunk_id
from config import (
    CHROMA_PATH,
    CHROMA_COLLECTION_NAME,
    EMB_MODEL,
    CHROMA_DISTANCE,
    RAW_PDFS,
    RAW_TXTS,
    INGEST_BATCH_SIZE,
    OLLAMA_HOST,
)

logger = logging.getLogger(__name__)


def iter_raw_texts() -> Iterator[tuple[str, str]]:
    """Yield (filename, text) from RAW_PDFS / RAW_TXTs. Skips files with errors."""
    RAW_PDFS.mkdir(parents=True, exist_ok=True)
    RAW_TXTS.mkdir(parents=True, exist_ok=True)

    # PDFs
    for p in sorted(RAW_PDFS.rglob("*.pdf")):
        try:
            txt = extract_text_from_pdf(p)
            if txt and txt.strip():
                yield (p.name, txt)
        except FileNotFoundError:
            logger.debug("File not found (skipping): %s", p)
        except Exception as e:
            logger.error("Failed to process PDF '%s' (skipping): %s", p, e)

    # TXTs
    for p in sorted(RAW_TXTS.rglob("*.txt")):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if txt.strip():
                yield (p.name, txt)
        except FileNotFoundError:
            logger.debug("File not found (skipping): %s", p)
        except Exception as e:
            logger.error("Failed to process TXT '%s' (skipping): %s", p, e)

def existing_ids(col, ids: list[str]) -> set[str]:
    """Return the subset of IDs that already exist in the collection (fast check)."""
    if not ids:
        return set()
    got = col.get(ids=ids, include=[])
    return set(got.get("ids", []))

@dataclass(slots=True)
class IngestStats:
    added: int = 0
    skipped: int = 0
    files: int = 0
    chunks: int = 0
    seconds: float = 0.0

def ingest(*, rebuild: bool = False, purge: bool = False, batch_size: int = INGEST_BATCH_SIZE) -> IngestStats:
    """
        - Gather raw texts (iter_raw_texts)
        - Chunk, hash, and ID them
        - Upsert into ChromaDB (Chroma embeds via embedding_function)
    """
    t0 = time.perf_counter()

    if purge:
        shutil.rmtree(CHROMA_PATH, ignore_errors=True)
        logger.info("Purged Chroma DB at %s", CHROMA_PATH)

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    if rebuild and not purge:
        try:
            client.delete_collection(CHROMA_COLLECTION_NAME)
        except Exception:
            pass

    ef = embedding_functions.OllamaEmbeddingFunction(
        url=f"{OLLAMA_HOST}/api/embeddings",
        model_name=EMB_MODEL,
    )

    col = client.get_or_create_collection(
        CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": CHROMA_DISTANCE},
        embedding_function=ef,
    )

    stats = IngestStats()
    ids_buf: list[str] = []
    docs_buf: list[str] = []
    meta_buf: list[dict] = []

    def flush() -> None:
        """Upload current batch to Chroma (dedupe before upsert)."""
        nonlocal ids_buf, docs_buf, meta_buf, stats
        if not ids_buf:
            return

        have = existing_ids(col, ids_buf)
        keep_idx = [i for i, _id in enumerate(ids_buf) if _id not in have]

        if keep_idx:
            new_ids  = [ids_buf[i]  for i in keep_idx]
            new_docs = [docs_buf[i] for i in keep_idx]
            new_meta = [meta_buf[i] for i in keep_idx]

            col.upsert(
                ids=new_ids,
                documents=new_docs,
                metadatas=new_meta,
            )
            stats.added += len(new_ids)

        stats.skipped += len(have)
        logger.debug("Flush: new=%s skipped=%s buffer_cleared", len(keep_idx), len(have))

        ids_buf.clear()
        docs_buf.clear()
        meta_buf.clear()

    for fname, full_text in iter_raw_texts():
        stats.files += 1
        for idx, ch in enumerate(chunk_text(full_text)):
            stats.chunks += 1

            digest = hash_text(ch)
            cid = stable_chunk_id(Path(fname).stem, idx, digest)

            ids_buf.append(cid)
            docs_buf.append(ch)
            meta_buf.append({
                "file": fname,
                "chunk_index": idx,
                "digest": digest,
                "type": "pdf" if fname.lower().endswith(".pdf") else "txt",
                "source_path": str(RAW_PDFS / fname) if fname.lower().endswith(".pdf") else str(RAW_TXTS / fname),
            })

            if len(ids_buf) >= batch_size:
                flush()

    flush()
    stats.seconds = time.perf_counter() - t0

    logger.info(
        "Ingest finished: files=%s chunks=%s added=%s skipped=%s secs=%.2f",
        stats.files, stats.chunks, stats.added, stats.skipped, stats.seconds
    )
    return stats

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest PDFs/TXTs into ChromaDB (Chroma performs embeddings via Ollama)."
    )
    parser.add_argument("--rebuild", action="store_true", help="Drop & recreate the collection before ingest.")
    parser.add_argument("--purge", action="store_true", help="Delete entire Chroma DB directory before ingest.")
    parser.add_argument("--batch", type=int, default=INGEST_BATCH_SIZE, help=f"Upsert batch size. Default: {INGEST_BATCH_SIZE}")
    return parser.parse_args()

def main() -> None:
    args = _parse_args()
    try:
        s = ingest(rebuild=args.rebuild, purge=args.purge, batch_size=int(args.batch))
        print(
            f"ingest_done files={s.files} chunks={s.chunks} added={s.added} "
            f"skipped={s.skipped} secs={s.seconds:.2f}"
        )
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
