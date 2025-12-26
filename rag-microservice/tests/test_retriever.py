"""Unit tests for document retrieval logic."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.retriever import (
    _distances_to_similarities,
    _clamp_overrides,
    query_chroma
)


def test_distances_to_similarities_cosine():
    """Test cosine distance to similarity conversion."""
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.CHROMA_DISTANCE = "cosine"
        distances = [0.0, 0.25, 0.5, 1.0]
        similarities = _distances_to_similarities(distances)
        
        assert similarities == [1.0, 0.75, 0.5, 0.0]


def test_distances_to_similarities_l2():
    """Test L2 distance to similarity conversion."""
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.CHROMA_DISTANCE = "l2"
        distances = [0.0, 1.0, 4.0]
        similarities = _distances_to_similarities(distances)
        
        assert similarities[0] == 1.0  # 1 / (1 + 0)
        assert similarities[1] == 0.5  # 1 / (1 + 1)
        assert similarities[2] == 0.2  # 1 / (1 + 4)


def test_distances_to_similarities_ip():
    """Test inner product distance to similarity conversion."""
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.CHROMA_DISTANCE = "ip"
        distances = [-0.8, -0.5, -0.1]
        similarities = _distances_to_similarities(distances)
        
        assert similarities == [0.8, 0.5, 0.1]


def test_clamp_overrides_uses_defaults():
    """Test clamp_overrides uses config defaults when no overrides provided."""
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.RETRIEVAL_K = 5
        mock_settings.MIN_SIMILARITY = 0.6
        
        k, min_sim = _clamp_overrides(None, None)
        
        assert k == 5
        assert min_sim == 0.6


def test_clamp_overrides_applies_limits():
    """Test clamp_overrides enforces min/max limits."""
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.RETRIEVAL_K = 5
        mock_settings.MIN_SIMILARITY = 0.6
        
        # Test k clamping
        k_low, _ = _clamp_overrides(0, None)
        k_high, _ = _clamp_overrides(100, None)
        
        assert k_low == 1  # _MIN_K
        assert k_high == 50  # _MAX_K
        
        # Test similarity clamping (only for cosine)
        mock_settings.CHROMA_DISTANCE = "cosine"
        _, sim_low = _clamp_overrides(None, -0.5)
        _, sim_high = _clamp_overrides(None, 1.5)
        
        assert sim_low == 0.0  # _MIN_SIM
        assert sim_high == 1.0  # _MAX_SIM (only clamped for cosine)


def test_clamp_overrides_accepts_valid_values():
    """Test clamp_overrides accepts valid override values."""
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.RETRIEVAL_K = 5
        mock_settings.MIN_SIMILARITY = 0.6
        
        k, min_sim = _clamp_overrides(10, 0.75)
        
        assert k == 10
        assert min_sim == 0.75


@pytest.mark.asyncio
async def test_query_chroma_success(sample_retrieval_results):
    """Test successful document retrieval with filtering."""
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.CHROMA_DISTANCE = "cosine"
        mock_settings.RETRIEVAL_K = 5
        mock_settings.MIN_SIMILARITY = 0.65
        
        # Mock ChromaDB collection
        mock_collection = MagicMock()
        mock_collection.query.return_value = sample_retrieval_results
        
        with patch("core.retriever.get_chroma_collection", return_value=mock_collection):
            results = query_chroma("What is Paris?", k=2, min_similarity=0.7)
            
            # Returns dict with documents/similarities keys
            assert len(results["documents"]) == 2
            assert results["documents"][0] == "Paris is the capital and largest city of France."
            assert results["similarities"][0] == 0.85  # 1.0 - 0.15
            assert results["similarities"][1] == 0.75  # 1.0 - 0.25


@pytest.mark.asyncio
async def test_query_chroma_filters_low_similarity():
    """Test that documents below min_similarity threshold are filtered out."""
    retrieval_results = {
        "ids": [["doc1", "doc2", "doc3"]],
        "documents": [[
            "Relevant document",
            "Somewhat relevant",
            "Not relevant"
        ]],
        "metadatas": [[
            {"source": "test.txt"},
            {"source": "test.txt"},
            {"source": "test.txt"}
        ]],
        "distances": [[0.1, 0.3, 0.6]]  # cosine distances
    }
    
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.CHROMA_DISTANCE = "cosine"
        mock_settings.RETRIEVAL_K = 5
        mock_settings.MIN_SIMILARITY = 0.65
        
        mock_collection = MagicMock()
        mock_collection.query.return_value = retrieval_results
        
        with patch("core.retriever.get_chroma_collection", return_value=mock_collection):
            results = query_chroma("test query", k=3, min_similarity=0.65)
            
            # Only first two should pass (similarities 0.9 and 0.7, third is 0.4)
            assert len(results["documents"]) == 2
            assert results["similarities"][0] == 0.9
            assert results["similarities"][1] == 0.7


@pytest.mark.asyncio
async def test_query_chroma_empty_results():
    """Test handling of empty ChromaDB results."""
    empty_results = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]]
    }
    
    with patch("core.retriever.settings") as mock_settings:
        mock_settings.CHROMA_DISTANCE = "cosine"
        mock_settings.RETRIEVAL_K = 5
        mock_settings.MIN_SIMILARITY = 0.65
        
        mock_collection = MagicMock()
        mock_collection.query.return_value = empty_results
        
        with patch("core.retriever.get_chroma_collection", return_value=mock_collection):
            results = query_chroma("query with no results")
            
            assert results["documents"] == []
            assert results["similarities"] == []

