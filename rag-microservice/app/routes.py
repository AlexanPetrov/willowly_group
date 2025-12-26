"""FastAPI routes for the RAG microservice."""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.schemas import QueryRequest, QueryResponse, DocumentMetadata, HealthCheckResponse
from app.auth import decode_access_token
from app.logger import logger
from app.config import settings
from core.retriever import query_chroma, get_chroma_collection
from core.generator import generate_response

import httpx

router = APIRouter(prefix="/v1")

auth_scheme = HTTPBearer(auto_error=True)


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    """Dependency to validate JWT token and extract user ID from 'sub' claim."""
    try:
        token = creds.credentials
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Run RAG query",
    description="Retrieves documents and generates a response using the RAG pipeline.",
)
async def rag_query(
    request: QueryRequest,
    user_id: str = Depends(get_current_user),
) -> QueryResponse:
    """Retrieve top-k chunks from Chroma and generate an answer grounded in context."""
    logger.debug("User %s asked: %s", user_id, request.text)
    logger.info("User %s made a query", user_id)
    
    try:
        results = await run_in_threadpool(
            query_chroma, request.text, request.k, request.min_similarity
        )

        docs = results["documents"]
        sims = results["similarities"]
        metas = results.get("metadatas", [])
        raw_distances = results.get("raw_distances", [])
        retrieved_count = len(results.get("similarities", []))  # Before filtering
        
        # Log retrieval metrics
        top_similarity = sims[0] if sims else None
        logger.info(
            "RAG retrieval stats: retrieved=%d, filtered=%d, top_sim=%s",
            retrieved_count, len(sims), f"{top_similarity:.3f}" if top_similarity else "None"
        )

        if not docs:
            logger.debug("RAG query: no docs passed threshold (k=%s, min_sim=%s)",
                         request.k, request.min_similarity)
            return QueryResponse(
                response="No relevant documents found.",
                context_docs=[],
                similarities=[],
                metadata=[],
                retrieval_stats={
                    "retrieved_count": retrieved_count,
                    "filtered_count": 0,
                    "top_similarity": None
                }
            )

        # Build metadata response
        metadata_objs = [
            DocumentMetadata(
                file=meta.get("file"),
                source_path=meta.get("source_path"),
                extra={k: v for k, v in (meta or {}).items() if k not in ["file", "source_path"]}
            )
            for meta in metas
        ]

        context = "\n\n".join(docs)

        if request.stream:
            gen_iter = await run_in_threadpool(
                generate_response, request.text, context, max_tokens=request.max_tokens, stream=True
            )
            answer = "".join(part for part in gen_iter)
        else:
            answer = await run_in_threadpool(
                generate_response, request.text, context, max_tokens=request.max_tokens, stream=False
            )

        return QueryResponse(
            response=answer,
            context_docs=docs,
            similarities=sims,
            metadata=metadata_objs,
            retrieval_stats={
                "retrieved_count": retrieved_count,
                "filtered_count": len(sims),
                "top_similarity": top_similarity
            }
        )

    except (httpx.HTTPError, Exception) as e:
        # Catch upstream errors (Chroma, Ollama, httpx) and other issues
        logger.exception("Error during /query: %s", e)
        if isinstance(e, httpx.HTTPError):
            raise HTTPException(status_code=502, detail=f"Upstream service error: {e}") from e
        raise HTTPException(status_code=500, detail="Internal server error") from e

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Service health check",
    description="Returns service status and configuration details.",
)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint returning service status and ChromaDB stats."""
    try:
        col = await run_in_threadpool(get_chroma_collection)
        count = await run_in_threadpool(col.count)

        return HealthCheckResponse(
            status="healthy",
            models={"generator": settings.GEN_MODEL},
            ctx={"num_ctx": settings.NUM_CTX},
            retrieval={
                "collection": settings.CHROMA_COLLECTION_NAME,
                "distance": settings.CHROMA_DISTANCE,
                "k_default": settings.RETRIEVAL_K,
                "min_similarity_default": settings.MIN_SIMILARITY,
                "count": count,
            },
            error=None,
        )
    except Exception as e:
        logger.exception("Health check degraded: %s", e)
        return HealthCheckResponse(
            status="degraded",
            models={},
            ctx={},
            retrieval={},
            error=str(e),
        )
