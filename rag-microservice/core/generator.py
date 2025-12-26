"""Generate answers from query and context using Ollama LLM."""

from collections.abc import Iterator, Iterable
import logging
import time
import ollama  # type: ignore
from app.config import settings

logger = logging.getLogger("rag_microservice.generator")

# Initialize Ollama client with the configured host
client = ollama.Client(host=settings.OLLAMA_HOST)

# Retry configuration
MAX_RETRIES = 3
BASE_RETRY_DELAY = 0.5  # seconds


def _build_prompt(query: str, context: str) -> str:
    """Construct a grounded prompt using provided context to avoid hallucinations."""
    base_instr = (
        "You are a helpful assistant. Answer strictly using the provided context. "
        "If the context is insufficient, say you don't know or that the documents "
        "do not contain the answer."
    )
    instructions = (
        base_instr if context.strip()
        else base_instr + " (Note: no context was provided.)"
    )

    # Token-based context truncation to stay within context window limits
    # Estimate: ~1 token per word on average (conservative estimate)
    words = context.split()
    max_context_tokens = max(64, int(settings.NUM_CTX * 0.65))
    truncated_words = words[:max_context_tokens]
    ctx_snippet = " ".join(truncated_words)

    return (
        f"{instructions}\n\n"
        f"Context:\n{ctx_snippet}\n\n"
        f"Question: {query}\n"
        f"Answer:"
    )

def _stream_generator(ollama_iter: Iterable[dict]) -> Iterator[str]:
    """Yield only non-empty text chunks from Ollama's streaming iterator."""
    for chunk in ollama_iter:
        part = chunk.get("response", "")
        if part:
            yield part

def generate_response(
    query: str,
    context: str,
    *,
    max_tokens: int = settings.NUM_PREDICT,
    stream: bool = False,
) -> str | Iterator[str]:
    """Generate an answer from the LLM using the retrieved context.
    
    Implements exponential backoff retry logic for transient failures.
    """
    max_tokens = max(1, int(max_tokens))
    prompt = _build_prompt(query, context or "")
    opts = {
        "temperature": settings.TEMPERATURE,
        "num_ctx": settings.NUM_CTX,
        "num_predict": max_tokens,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.generate(
                model=settings.GEN_MODEL,
                prompt=prompt,
                stream=stream,
                options=opts,
            )
            if stream:
                return _stream_generator(resp)
            return (resp.get("response") or "").strip()
        
        except (ConnectionError, TimeoutError, ollama.ResponseError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                logger.warning(
                    "Ollama generation attempt %d/%d failed: %s. Retrying in %.2fs...",
                    attempt + 1, MAX_RETRIES, str(e), delay
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Ollama generation failed after %d attempts: %s",
                    MAX_RETRIES, str(e)
                )
    
    raise last_error
