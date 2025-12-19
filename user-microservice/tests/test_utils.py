"""
Unit tests for utility functions.
Tests simple, isolated utility functions without dependencies.
"""

import pytest
from app.utils import normalize_email


class TestNormalizeEmail:
    """Test the normalize_email utility function."""
    
    def test_lowercase_conversion(self):
        """Test that email is converted to lowercase."""
        assert normalize_email("TEST@EXAMPLE.COM") == "test@example.com"
        assert normalize_email("Test@Example.Com") == "test@example.com"
    
    def test_whitespace_stripping(self):
        """Test that leading/trailing whitespace is removed."""
        assert normalize_email("  test@example.com  ") == "test@example.com"
        assert normalize_email("\ttest@example.com\n") == "test@example.com"
    
    def test_combined_normalization(self):
        """Test combined lowercase and whitespace handling."""
        assert normalize_email("  TEST@EXAMPLE.COM  ") == "test@example.com"
        assert normalize_email("\n  Test@Example.Com  \t") == "test@example.com"
    
    def test_already_normalized(self):
        """Test that already normalized emails pass through unchanged."""
        assert normalize_email("test@example.com") == "test@example.com"
    
    def test_empty_string(self):
        """Test handling of empty string."""
        assert normalize_email("") == ""
        assert normalize_email("   ") == ""
    
    def test_preserves_special_characters(self):
        """Test that special characters in email are preserved."""
        assert normalize_email("test+tag@example.com") == "test+tag@example.com"
        assert normalize_email("test.name@example.com") == "test.name@example.com"
        assert normalize_email("test_name@example.com") == "test_name@example.com"
