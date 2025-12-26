"""Tests for recent RAG microservice improvements.

Tests for:
- Input validation boundaries
- Response structure (metadata, retrieval_stats)
- Retry logic with exponential backoff
- Streaming format validation
"""

import pytest
from unittest.mock import patch, MagicMock
import time
from core.generator import generate_response, MAX_RETRIES, BASE_RETRY_DELAY


# ==================== INPUT VALIDATION BOUNDARY TESTS ====================

@pytest.mark.asyncio
async def test_query_k_below_minimum(client, valid_token):
    """Test query with k < 1 is rejected."""
    response = await client.post(
        "/api/v1/query",
        json={
            "text": "test",
            "k": 0,  # Below minimum (1)
            "min_similarity": 0.65,
            "max_tokens": 512
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_query_k_above_maximum(client, valid_token):
    """Test query with k > 20 is rejected."""
    response = await client.post(
        "/api/v1/query",
        json={
            "text": "test",
            "k": 21,  # Above maximum (20)
            "min_similarity": 0.65,
            "max_tokens": 512
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_query_similarity_below_minimum(client, valid_token):
    """Test query with min_similarity < 0.0 is rejected."""
    response = await client.post(
        "/api/v1/query",
        json={
            "text": "test",
            "k": 5,
            "min_similarity": -0.1,  # Below minimum (0.0)
            "max_tokens": 512
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_query_similarity_above_maximum(client, valid_token):
    """Test query with min_similarity > 1.0 is rejected."""
    response = await client.post(
        "/api/v1/query",
        json={
            "text": "test",
            "k": 5,
            "min_similarity": 1.1,  # Above maximum (1.0)
            "max_tokens": 512
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_query_max_tokens_below_minimum(client, valid_token):
    """Test query with max_tokens < 1 is rejected."""
    response = await client.post(
        "/api/v1/query",
        json={
            "text": "test",
            "k": 5,
            "min_similarity": 0.65,
            "max_tokens": 0  # Below minimum (1)
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_query_max_tokens_above_maximum(client, valid_token):
    """Test query with max_tokens > 2048 is rejected."""
    response = await client.post(
        "/api/v1/query",
        json={
            "text": "test",
            "k": 5,
            "min_similarity": 0.65,
            "max_tokens": 2049  # Above maximum (2048)
        },
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_query_k_at_boundaries(client, valid_token):
    """Test query with k at valid boundaries (1 and 20) accepted."""
    # This test assumes mock retrieval works
    with patch("app.routes.query_chroma") as mock_retriever:
        mock_retriever.return_value = {
            "documents": ["test doc"],
            "similarities": [0.8],
            "metadatas": [{"file": "test.pdf", "source_path": "test.pdf"}],
            "raw_distances": [0.2]
        }
        
        with patch("app.routes.generate_response") as mock_gen:
            mock_gen.return_value = "test answer"
            
            # Test k=1
            response = await client.post(
                "/api/v1/query",
                json={"text": "test", "k": 1, "min_similarity": 0.65, "max_tokens": 512},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            assert response.status_code == 200
            
            # Test k=20
            response = await client.post(
                "/api/v1/query",
                json={"text": "test", "k": 20, "min_similarity": 0.65, "max_tokens": 512},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            assert response.status_code == 200


# ==================== RESPONSE STRUCTURE TESTS ====================

@pytest.mark.asyncio
async def test_query_response_includes_metadata(client, valid_token):
    """Test query response includes document metadata."""
    with patch("app.routes.query_chroma") as mock_retriever:
        mock_retriever.return_value = {
            "documents": ["Lions are apex predators"],
            "similarities": [0.85],
            "metadatas": [{"file": "animals.pdf", "source_path": "data/animals.pdf", "chunk_index": 0}],
            "raw_distances": [0.15]
        }
        
        with patch("app.routes.generate_response") as mock_gen:
            mock_gen.return_value = "Lions are large cats."
            
            response = await client.post(
                "/api/v1/query",
                json={"text": "test", "k": 1},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify metadata structure
            assert "metadata" in data
            assert isinstance(data["metadata"], list)
            assert len(data["metadata"]) == 1
            
            metadata = data["metadata"][0]
            assert metadata["file"] == "animals.pdf"
            assert metadata["source_path"] == "data/animals.pdf"
            assert "extra" in metadata
            assert metadata["extra"]["chunk_index"] == 0


@pytest.mark.asyncio
async def test_query_response_includes_retrieval_stats(client, valid_token):
    """Test query response includes retrieval statistics."""
    with patch("app.routes.query_chroma") as mock_retriever:
        # Simulate retrieval that filtered results
        mock_retriever.return_value = {
            "documents": ["filtered doc"],
            "similarities": [0.8],
            "metadatas": [{"file": "test.pdf", "source_path": "test.pdf"}],
            "raw_distances": [0.2]
        }
        
        with patch("app.routes.generate_response") as mock_gen:
            mock_gen.return_value = "answer"
            
            response = await client.post(
                "/api/v1/query",
                json={"text": "test", "k": 5},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify retrieval_stats structure
            assert "retrieval_stats" in data
            stats = data["retrieval_stats"]
            assert "retrieved_count" in stats
            assert "filtered_count" in stats
            assert "top_similarity" in stats
            assert stats["filtered_count"] > 0
            assert 0.0 <= stats["top_similarity"] <= 1.0


@pytest.mark.asyncio
async def test_query_response_no_results_has_stats(client, valid_token):
    """Test that no-results response still includes retrieval stats."""
    with patch("app.routes.query_chroma") as mock_retriever:
        # Return no matching documents
        mock_retriever.return_value = {
            "documents": [],
            "similarities": [],
            "metadatas": [],
            "raw_distances": []
        }
        
        response = await client.post(
            "/api/v1/query",
            json={"text": "nonexistent topic", "k": 5},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure even with no results
        assert "response" in data
        assert "No relevant documents found" in data["response"]
        assert "retrieval_stats" in data
        assert data["retrieval_stats"]["filtered_count"] == 0
        assert data["retrieval_stats"]["top_similarity"] is None


# ==================== RETRY LOGIC TESTS ====================

def test_generate_response_succeeds_on_first_attempt():
    """Test generate_response succeeds without retries."""
    with patch("core.generator.settings") as mock_settings:
        mock_settings.NUM_CTX = 4096
        mock_settings.NUM_PREDICT = 512
        mock_settings.TEMPERATURE = 0.25
        mock_settings.GEN_MODEL = "llama3.1:8b"
        
        mock_response = {"response": "test answer"}
        
        with patch("core.generator.client.generate", return_value=mock_response) as mock_gen:
            result = generate_response("query", "context")
            
            assert result == "test answer"
            # Should only call once if successful
            assert mock_gen.call_count == 1


def test_generate_response_retries_on_connection_error():
    """Test generate_response retries on connection failures."""
    with patch("core.generator.settings") as mock_settings:
        mock_settings.NUM_CTX = 4096
        mock_settings.NUM_PREDICT = 512
        mock_settings.TEMPERATURE = 0.25
        mock_settings.GEN_MODEL = "llama3.1:8b"
        
        # Fail twice, succeed on third attempt
        mock_response = {"response": "test answer"}
        
        with patch("core.generator.client.generate") as mock_gen:
            mock_gen.side_effect = [
                ConnectionError("Connection failed"),
                ConnectionError("Connection failed"),
                mock_response
            ]
            
            with patch("core.generator.time.sleep"):  # Skip actual sleep delays
                result = generate_response("query", "context")
            
            assert result == "test answer"
            # Should have retried twice before succeeding
            assert mock_gen.call_count == 3


def test_generate_response_fails_after_max_retries():
    """Test generate_response fails after exhausting retries."""
    with patch("core.generator.settings") as mock_settings:
        mock_settings.NUM_CTX = 4096
        mock_settings.NUM_PREDICT = 512
        mock_settings.TEMPERATURE = 0.25
        mock_settings.GEN_MODEL = "llama3.1:8b"
        
        with patch("core.generator.client.generate") as mock_gen:
            mock_gen.side_effect = ConnectionError("Connection failed")
            
            with patch("core.generator.time.sleep"):  # Skip actual sleep delays
                with pytest.raises(ConnectionError):
                    generate_response("query", "context")
            
            # Should have attempted MAX_RETRIES times
            assert mock_gen.call_count == MAX_RETRIES


def test_generate_response_exponential_backoff():
    """Test generate_response uses exponential backoff for retries."""
    with patch("core.generator.settings") as mock_settings:
        mock_settings.NUM_CTX = 4096
        mock_settings.NUM_PREDICT = 512
        mock_settings.TEMPERATURE = 0.25
        mock_settings.GEN_MODEL = "llama3.1:8b"
        
        with patch("core.generator.client.generate") as mock_gen:
            mock_gen.side_effect = ConnectionError("Connection failed")
            
            with patch("core.generator.time.sleep") as mock_sleep:
                with pytest.raises(ConnectionError):
                    generate_response("query", "context")
                
                # Should have called sleep with exponential delays
                # 1st retry: 0.5 * 2^0 = 0.5
                # 2nd retry: 0.5 * 2^1 = 1.0
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                
                assert len(sleep_calls) == MAX_RETRIES - 1
                # Verify exponential pattern
                assert abs(sleep_calls[0] - 0.5) < 0.01
                assert abs(sleep_calls[1] - 1.0) < 0.01


# ==================== STREAMING FORMAT VALIDATION ====================

@pytest.mark.asyncio
async def test_query_streaming_enabled_returns_full_response(client, valid_token):
    """Test that stream=true still returns complete response (not streamed chunks)."""
    with patch("app.routes.query_chroma") as mock_retriever:
        mock_retriever.return_value = {
            "documents": ["test doc"],
            "similarities": [0.85],
            "metadatas": [{"file": "test.pdf", "source_path": "test.pdf"}],
            "raw_distances": [0.15]
        }
        
        # Simulate streaming chunks that get concatenated
        chunks = ["Hello", " ", "world", "!"]
        
        with patch("app.routes.generate_response") as mock_gen:
            mock_gen.return_value = iter(chunks)  # Return iterator for streaming
            
            response = await client.post(
                "/api/v1/query",
                json={"text": "test", "stream": True},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should have concatenated all chunks
            assert data["response"] == "Hello world!"
            # Should still include metadata and stats
            assert "metadata" in data
            assert "retrieval_stats" in data


@pytest.mark.asyncio
async def test_query_non_streaming_default(client, valid_token):
    """Test that stream=false (default) returns complete response."""
    with patch("app.routes.query_chroma") as mock_retriever:
        mock_retriever.return_value = {
            "documents": ["test doc"],
            "similarities": [0.85],
            "metadatas": [{"file": "test.pdf", "source_path": "test.pdf"}],
            "raw_distances": [0.15]
        }
        
        with patch("app.routes.generate_response") as mock_gen:
            mock_gen.return_value = "complete response"
            
            response = await client.post(
                "/api/v1/query",
                json={"text": "test"},  # stream not specified, defaults to False
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["response"] == "complete response"
            assert "metadata" in data
            assert "retrieval_stats" in data
