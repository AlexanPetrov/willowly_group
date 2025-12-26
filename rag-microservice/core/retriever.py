"""Embeds user query into a vector.
   Asks ChromaDB, which document chunks are closest to this query”.
   Applies filtering (similarity threshold, top-k).
   Returns best-matching text chunks + metadata, using embeddings.
"""

import logging
import chromadb  # type: ignore
from app.config import settings

logger = logging.getLogger("rag_microservice.retriever")

_MIN_K: int = 1
_MAX_K: int = 50
_MIN_SIM: float = 0.0
_MAX_SIM: float = 1.0

_client = None
_collection = None


def _client_cached():
    """Memoize a single PersistentClient per process."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(settings.CHROMA_PATH))
    return _client

def get_chroma_collection():
    """Get the existing collection without modifying embedding function."""
    global _collection
    if _collection is None:
        _collection = _client_cached().get_collection(settings.CHROMA_COLLECTION_NAME)
    return _collection

def _distances_to_similarities(distances: list[float]) -> list[float]:
    """Convert Chroma distances to similarity scores (higher = more similar)."""
    if settings.CHROMA_DISTANCE == "cosine":
        return [1.0 - d for d in distances]
    elif settings.CHROMA_DISTANCE == "l2":
        return [1.0 / (1.0 + d) for d in distances]
    else:  # "ip"
        return [-d for d in distances]

def _clamp_overrides(k: int | None, min_similarity: float | None) -> tuple[int, float]:
    """Apply config defaults and clamp to safe ranges."""
    effective_k = settings.RETRIEVAL_K if k is None else int(k)
    effective_k = max(_MIN_K, min(_MAX_K, effective_k))

    effective_min_sim = settings.MIN_SIMILARITY if min_similarity is None else float(min_similarity)
    if settings.CHROMA_DISTANCE == "cosine":
        effective_min_sim = max(_MIN_SIM, min(_MAX_SIM, effective_min_sim))
    else:
        # "l2" and "ip" similarity
        effective_min_sim = max(_MIN_SIM, effective_min_sim)

    return effective_k, effective_min_sim

def query_chroma(
    query_text: str,
    k: int | None = None,
    min_similarity: float | None = None,
) -> dict[str, list]:
    """Query Chroma by text and return top documents filtered by similarity."""
    collection = get_chroma_collection()
    effective_k, effective_min_sim = _clamp_overrides(k, min_similarity)

    result = collection.query(
        query_texts=[query_text],
        n_results=effective_k,
        include=["documents", "distances", "metadatas"],
    )

    docs_outer = result.get("documents", [])
    dists_outer = result.get("distances", [])
    metas_outer = result.get("metadatas", [])

    if not docs_outer:
        logger.debug(
            "RAG retrieval: collection empty or no hits | k=%s min_sim=%.3f metric=%s",
            effective_k,
            effective_min_sim,
            settings.CHROMA_DISTANCE,
        )
        return {
            "documents": [],
            "similarities": [],
            "metadatas": [],
            "raw_distances": [],
            "metric": settings.CHROMA_DISTANCE,
        }

    documents = docs_outer[0]
    distances = dists_outer[0] if dists_outer else []
    metadatas = metas_outer[0] if metas_outer else [{} for _ in documents]

    n = min(len(documents), len(distances), len(metadatas))
    if not (len(documents) == len(distances) == len(metadatas)):
        logger.warning(
            "RAG retrieval: length mismatch (docs=%s dists=%s metas=%s) -> truncating to %s",
            len(documents), len(distances), len(metadatas), n
        )
        documents = documents[:n]
        distances = distances[:n]
        metadatas = metadatas[:n]

    similarities = _distances_to_similarities(distances)

    ranked = sorted(
        zip(documents, similarities, metadatas, distances),
        key=lambda x: x[1],
        reverse=True,
    )

    kept_docs: list[str] = []
    kept_sims: list[float] = []
    kept_meta: list[dict] = []
    kept_dists: list[float] = []

    for doc, sim, meta, dist in ranked:
        if sim >= effective_min_sim:
            kept_docs.append(doc)
            kept_sims.append(sim)
            kept_meta.append(meta)
            kept_dists.append(dist)

    if not kept_docs:
        top_preview = [
            {
                "sim": s,
                "dist": d,
                "file": (m or {}).get("file"),
                "source_path": (m or {}).get("source_path"),
            }
            for _, s, m, d in ranked[:3]
        ]
        logger.debug(
            "RAG retrieval: 0 docs passed threshold | k=%s min_sim=%.3f metric=%s top_preview=%s",
            effective_k,
            effective_min_sim,
            settings.CHROMA_DISTANCE,
            top_preview,
        )
    else:
        logger.debug(
            "RAG retrieval: kept=%s / %s (k=%s, min_sim=%.3f, metric=%s)",
            len(kept_docs), len(ranked), effective_k, effective_min_sim, settings.CHROMA_DISTANCE
        )

    return {
        "documents": kept_docs,
        "similarities": kept_sims,
        "metadatas": kept_meta,
        "raw_distances": kept_dists,
        "metric": settings.CHROMA_DISTANCE,
    }
    