# Creates text embeddings via Ollama's embedding model (with retries and optional normalization).

import time
import math
import ollama
from config import EMB_MODEL, OLLAMA_HOST


def _l2_normalize(vec: list[float]) -> list[float]:
    """Normalize a vector to unit length (recommended for cosine similarity)."""
    n = math.sqrt(sum(x * x for x in vec))
    return [x / n for x in vec] if n > 0 else vec

def get_embeddings(
    text: str,
    *,
    normalize: bool = True,
    timeout: float = 30.0,
    retries: int = 3,
) -> list[float]:
    """Return a single embedding for `text` using Ollama; retry briefly on transient errors."""
    if not text or not text.strip():
        raise ValueError("get_embeddings: empty text")

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = ollama.embeddings(
                model=EMB_MODEL,
                prompt=text,
                options={"timeout": timeout},
                host=OLLAMA_HOST,
            )
            emb = resp["embedding"]
            return _l2_normalize(emb) if normalize else emb
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(0.5 * (2 ** attempt))
            else:
                raise ConnectionError(f"Embedding failed after {retries} attempts: {e}") from e
