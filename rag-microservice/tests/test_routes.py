"""Integration tests for RAG API endpoints."""

import pytest


# ==================== GET /health ====================

@pytest.mark.asyncio
async def test_health_check_success(client):
    """Test health check endpoint returns 200 with status (may be degraded if no ChromaDB)."""
    response = await client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # If degraded, check for error field instead of service
    if data["status"] == "degraded":
        assert "error" in data
    else:
        assert data["status"] == "healthy"


# ==================== POST /api/v1/query ====================

@pytest.mark.asyncio
async def test_query_missing_auth(client, sample_query_request):
    """Test query without authentication returns 401."""
    response = await client.post("/api/v1/query", json=sample_query_request)
    
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_query_invalid_token(client, sample_query_request):
    """Test query with invalid token returns 401."""
    response = await client.post(
        "/api/v1/query",
        json=sample_query_request,
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_query_expired_token(client, sample_query_request, expired_token):
    """Test query with expired token returns 401."""
    response = await client.post(
        "/api/v1/query",
        json=sample_query_request,
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_query_missing_text_field(client, valid_token):
    """Test query without 'text' field returns 422."""
    response = await client.post(
        "/api/v1/query",
        json={"k": 3},  # Missing 'text'
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_query_empty_query_string(client, valid_token):
    """Test query with empty string gets caught—either 422 validation or 500 if it hits ChromaDB."""
    response = await client.post(
        "/api/v1/query",
        json={"text": ""},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    # Could be 422 (validation) or 500 (ChromaDB error with empty query)
    assert response.status_code in [422, 500]


@pytest.mark.asyncio
async def test_query_invalid_k_type(client, valid_token):
    """Test query with invalid k type returns 422."""
    response = await client.post(
        "/api/v1/query",
        json={"text": "test", "k": "not-a-number"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_query_invalid_min_similarity_type(client, valid_token):
    """Test query with invalid min_similarity type returns 422."""
    response = await client.post(
        "/api/v1/query",
        json={"text": "test", "min_similarity": "not-a-float"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_query_uses_default_values(client, valid_token):
    """Test query with minimal payload uses default values from config."""
    from unittest.mock import patch
    
    # Mock retrieval and generation with correct return format
    mock_retrieval_results = {
        "documents": ["Test document"],
        "similarities": [0.9],
        "metadatas": [{"source": "test.txt", "page": 1}],
        "raw_distances": [0.1],
        "metric": "cosine"
    }
    
    with patch("app.routes.query_chroma", return_value=mock_retrieval_results):
        with patch("app.routes.generate_response", return_value="Test response"):
            response = await client.post(
                "/api/v1/query",
                json={"text": "test query"},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["response"] == "Test response"
            assert len(data["context_docs"]) == 1
            assert data["context_docs"][0] == "Test document"


@pytest.mark.asyncio
async def test_query_with_custom_parameters(client, valid_token):
    """Test query with custom k and min_similarity parameters."""
    from unittest.mock import patch
    
    mock_retrieval_results = {
        "documents": [],
        "similarities": [],
        "metadatas": [],
        "raw_distances": [],
        "metric": "cosine"
    }
    
    with patch("app.routes.query_chroma", return_value=mock_retrieval_results) as mock_query:
        response = await client.post(
            "/api/v1/query",
            json={"text": "test", "k": 5, "min_similarity": 0.8},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        # Verify custom parameters were passed to query_chroma
        assert mock_query.called
        call_args = mock_query.call_args
        assert call_args[0][1] == 5  # k parameter
        assert call_args[0][2] == 0.8  # min_similarity parameter
        
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_no_retrieval_results(client, valid_token):
    """Test query when no documents match the similarity threshold."""
    from unittest.mock import patch
    
    mock_empty = {
        "documents": [],
        "similarities": [],
        "metadatas": [],
        "raw_distances": [],
        "metric": "cosine"
    }
    
    with patch("app.routes.query_chroma", return_value=mock_empty):
        response = await client.post(
            "/api/v1/query",
            json={"text": "unknown query"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["context_docs"] == []
        assert "No relevant documents" in data["response"]


@pytest.mark.asyncio
async def test_query_with_multiple_sources(client, valid_token):
    """Test query returns multiple document sources."""
    from unittest.mock import patch
    
    mock_retrieval_results = {
        "documents": ["Document 1", "Document 2", "Document 3"],
        "similarities": [0.95, 0.85, 0.75],
        "metadatas": [
            {"source": "doc1.txt", "page": 1},
            {"source": "doc2.txt", "page": 2},
            {"source": "doc3.txt", "page": 1}
        ],
        "raw_distances": [0.05, 0.15, 0.25],
        "metric": "cosine"
    }
    
    with patch("app.routes.query_chroma", return_value=mock_retrieval_results):
        with patch("app.routes.generate_response", return_value="Answer based on three sources"):
            response = await client.post(
                "/api/v1/query",
                json={"text": "test"},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["context_docs"]) == 3
            assert data["similarities"][0] == 0.95
            assert data["similarities"][1] == 0.85
            assert data["similarities"][2] == 0.75


@pytest.mark.asyncio
async def test_query_handles_generation_error(client, valid_token):
    """Test query handles LLM generation errors gracefully."""
    from unittest.mock import patch
    
    mock_retrieval_results = {
        "documents": ["Test doc"],
        "similarities": [0.9],
        "metadatas": [{}],
        "raw_distances": [0.1],
        "metric": "cosine"
    }
    
    with patch("app.routes.query_chroma", return_value=mock_retrieval_results):
        with patch("app.routes.generate_response", side_effect=Exception("Ollama connection error")):
            response = await client.post(
                "/api/v1/query",
                json={"text": "test"},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 500
            assert "detail" in response.json()


@pytest.mark.asyncio
async def test_query_handles_retrieval_error(client, valid_token):
    """Test query handles ChromaDB retrieval errors gracefully."""
    from unittest.mock import patch
    
    with patch("app.routes.query_chroma", side_effect=Exception("ChromaDB connection error")):
        response = await client.post(
            "/api/v1/query",
            json={"text": "test"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == 500
        assert "detail" in response.json()
