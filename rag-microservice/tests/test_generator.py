"""Unit tests for LLM response generation."""

import pytest
from unittest.mock import patch, MagicMock
from core.generator import (
    _build_prompt,
    _stream_generator,
    generate_response
)


def test_build_prompt_with_context():
    """Test prompt construction with valid context."""
    with patch("core.generator.settings") as mock_settings:
        mock_settings.NUM_CTX = 4096
        
        query = "What is Python?"
        context = "Python is a high-level programming language."
        
        prompt = _build_prompt(query, context)
        
        assert "helpful assistant" in prompt
        assert "Answer strictly using the provided context" in prompt
        assert "Context:" in prompt
        assert "Python is a high-level programming language" in prompt
        assert "Question: What is Python?" in prompt
        assert "Answer:" in prompt


def test_build_prompt_empty_context():
    """Test prompt construction with empty context."""
    with patch("core.generator.settings") as mock_settings:
        mock_settings.NUM_CTX = 4096
        
        query = "What is Python?"
        context = ""
        
        prompt = _build_prompt(query, context)
        
        assert "no context was provided" in prompt
        assert "Question: What is Python?" in prompt


def test_build_prompt_truncates_long_context():
    """Test that very long context is truncated to fit token limits."""
    with patch("core.generator.settings") as mock_settings:
        mock_settings.NUM_CTX = 100  # Small context window for testing
        
        # Create context with many words (will exceed 65% of 100 tokens)
        long_context = " ".join([f"word{i}" for i in range(1000)])
        
        prompt = _build_prompt("query", long_context)
        
        # Prompt should be shorter than original context
        assert len(prompt) < len(long_context)
        assert "Context:" in prompt


def test_stream_generator_yields_text_chunks():
    """Test streaming generator yields only text chunks."""
    ollama_iter = [
        {"response": "Hello"},
        {"response": " world"},
        {"response": ""},  # Empty chunks should be skipped
        {"response": "!"}
    ]
    
    chunks = list(_stream_generator(ollama_iter))
    
    assert chunks == ["Hello", " world", "!"]


def test_stream_generator_handles_missing_response_key():
    """Test streaming generator handles chunks without 'response' key."""
    ollama_iter = [
        {"response": "Hello"},
        {"other_key": "value"},  # No 'response' key
        {"response": "world"}
    ]
    
    chunks = list(_stream_generator(ollama_iter))
    
    assert chunks == ["Hello", "world"]



